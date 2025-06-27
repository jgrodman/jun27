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
        self._get_nodes()
        
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
    
    def _bind_pod_to_node(self, pod_name: str, namespace: str, node_name: str) -> bool:
        """Bind a pod to a node"""
        try:
            binding = client.V1Binding(
                metadata=client.V1ObjectMeta(name=pod_name),
                target=client.V1ObjectReference(
                    kind="Node",
                    name=node_name
                )
            )
            
            self.v1.create_namespaced_binding(
                namespace=namespace,
                body=binding
            )
            
            self.logger.info(f"Successfully bound pod {pod_name} to node {node_name}")
            return True
            
        except ApiException as e:
            self.logger.error(f"Failed to bind pod {pod_name} to node {node_name}: {e}")
            return False
    
    def _schedule_pod(self, pod):
        """Schedule a single pod to any available node"""
        self.logger.info("In _schedule_pod")
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        
        # Just pick the first available node (simple round-robin later)
        if self.nodes:
            node_name = self.nodes[0]  # Simple: always use first node for now
            self.logger.info(f"Scheduling pod {pod_name} to node {node_name}")
            return self._bind_pod_to_node(pod_name, namespace, node_name)
        else:
            self.logger.error(f"No available nodes to schedule pod {pod_name}")
            return False
    
    def run(self):
        """Main scheduler loop"""
        self.logger.info(f"Starting custom scheduler: {self.scheduler_name}")
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
            elif pod.spec.scheduler_name == self.scheduler_name:
                self.logger.info(f"DEBUG: Skipped pod {pod_name} - event_type={event_type}, node_name={pod.spec.node_name}")


if __name__ == "__main__":
    scheduler = CustomScheduler()
    scheduler.run()