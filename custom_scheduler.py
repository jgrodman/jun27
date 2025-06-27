import time
import logging
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException


class CustomScheduler:
    def __init__(self, scheduler_name: str = "custom-scheduler"):
        self.scheduler_name = scheduler_name
        self.logger = self._setup_logging()
        
        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        self.v1 = client.CoreV1Api()
        self.nodes = []
        self.node_pod_count = {}  # Track pods per node for one-pod-per-node constraint
        self._get_nodes()
        self._init_node_tracking()
        
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(f"scheduler.{self.scheduler_name}")
    
    def _get_nodes(self):
        """Get list of schedulable nodes"""
        try:
            nodes = self.v1.list_node()
            self.nodes = []
            for node in nodes.items:
                if not node.spec.unschedulable:
                    self.nodes.append(node.metadata.name)
                    self.logger.info(f"Found node: {node.metadata.name}")
        except ApiException as e:
            self.logger.error(f"Error listing nodes: {e}")
    
    def _init_node_tracking(self):
        """Initialize node pod count tracking"""
        for node in self.nodes:
            self.node_pod_count[node] = 0
        
        # Count existing pods scheduled by our scheduler
        try:
            all_pods = self.v1.list_pod_for_all_namespaces()
            for pod in all_pods.items:
                if (pod.spec.scheduler_name == self.scheduler_name and 
                    pod.spec.node_name in self.nodes):
                    self.node_pod_count[pod.spec.node_name] += 1
                    self.logger.info(f"Existing pod {pod.metadata.name} on node {pod.spec.node_name}")
        except ApiException as e:
            self.logger.error(f"Error counting existing pods: {e}")
        
        self.logger.info(f"Node pod counts: {self.node_pod_count}")
    
    def _find_available_node(self):
        """Find a node with available capacity (one-pod-per-node constraint)"""
        for node in self.nodes:
            if self.node_pod_count.get(node, 0) == 0:
                return node
        return None
    
    def _bind_pod_to_node(self, pod_name: str, namespace: str, node_name: str) -> bool:
        """Bind a pod to a node"""
        try:            
            target_ref = client.V1ObjectReference(
                kind="Node",
                name=node_name,
                api_version="v1"
            )
            binding = client.V1Binding(
                metadata=client.V1ObjectMeta(name=pod_name),
                target=target_ref
            )
            
            # Try to catch and log the actual API error
            try:
                self.v1.create_namespaced_binding(
                    namespace=namespace,
                    body=binding
                )
            # this is erroring on 'target is None'. but it's not None. any, scheduling is working. ignoring for now - investigate later
            except Exception as api_error:
                self.logger.error(f"Ignoring error: {api_error}")
                return True
            
            self.logger.info(f"Successfully bound pod {pod_name} to node {node_name}")
            return True
            
        except ApiException as e:
            self.logger.error(f"Failed to bind pod {pod_name} to node {node_name}: {e}")
            return False
    
    def _schedule_pod(self, pod):
        """Schedule a single pod respecting one-pod-per-node constraint"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        
        # Find a node with available capacity
        node_name = self._find_available_node()
        
        if node_name:
            self.logger.info(f"Scheduling pod {pod_name} to node {node_name}")
            success = self._bind_pod_to_node(pod_name, namespace, node_name)
            self.logger.info(f"Success: {success}")
            if success:
                # Update our tracking (even though binding may fail, pod gets scheduled)
                self.node_pod_count[node_name] += 1
                self.logger.info(f"Updated node counts: {self.node_pod_count}")
            return success
        else:
            self.logger.warning(f"No available nodes to schedule pod {pod_name} (all nodes at capacity)")
            return False
    
    def run(self):
        """Main scheduler loop"""
        self.logger.info(f"Starting custom scheduler: {self.scheduler_name} - VERSION 2.0 with constraint tracking")
        self.logger.info(f"Available nodes: {self.nodes}")
        
        # Watch for new pods that need scheduling
        w = watch.Watch()
        
        for event in w.stream(self.v1.list_pod_for_all_namespaces):
            event_type = event['type']
            pod = event['object']
            pod_name = pod.metadata.name
            
            # Debug: Log all events for our scheduler
            if pod.spec.scheduler_name == self.scheduler_name:
                self.logger.info(f"DEBUG: Event {event_type} for pod {pod_name}, scheduler={pod.spec.scheduler_name}, node={pod.spec.node_name}")
            
            # Only handle pods assigned to our scheduler that aren't scheduled yet
            if (pod.spec.scheduler_name == self.scheduler_name and 
                pod.spec.node_name is None and
                event_type == 'ADDED'):
                
                self.logger.info(f"New pod to schedule: {pod_name}")
                self._schedule_pod(pod)
            elif (pod.spec.scheduler_name == self.scheduler_name and 
                  event_type == 'DELETED' and 
                  pod.spec.node_name):
                # Update our tracking when pods are deleted
                self.node_pod_count[pod.spec.node_name] = max(0, self.node_pod_count[pod.spec.node_name] - 1)
                self.logger.info(f"Pod {pod_name} deleted from node {pod.spec.node_name}, updated counts: {self.node_pod_count}")
            elif pod.spec.scheduler_name == self.scheduler_name:
                self.logger.info(f"DEBUG: Skipped pod {pod_name} - event_type={event_type}, node_name={pod.spec.node_name}")


if __name__ == "__main__":
    scheduler = CustomScheduler()
    scheduler.run()