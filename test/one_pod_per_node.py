#!/usr/bin/env python3
"""
Multi-pod test for the custom Kubernetes scheduler

Test: Create multiple pods and verify one-pod-per-node constraint is enforced
"""

import time
import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException


def check_scheduler_health():
    """Check if the scheduler is running"""
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    
    v1 = client.CoreV1Api()
    
    print("Checking scheduler health...")
    try:
        pods = v1.list_namespaced_pod(namespace="scheduling", label_selector="app=custom-scheduler")
        
        if not pods.items:
            print("✗ No scheduler pods found")
            return False
            
        scheduler_pod = pods.items[0]
        print(f"✓ Scheduler pod: {scheduler_pod.metadata.name}")
        print(f"✓ Status: {scheduler_pod.status.phase}")
        print(f"✓ Node: {scheduler_pod.spec.node_name}")
        
        return scheduler_pod.status.phase == "Running"
        
    except ApiException as e:
        print(f"✗ Error checking scheduler: {e}")
        return False


def test_one_pod_per_node():
    """Test that the scheduler enforces one pod per node constraint"""
    
    # Set up Kubernetes client
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    
    v1 = client.CoreV1Api()
    namespace = "default"
    scheduler_name = "custom-scheduler"
    
    print("=" * 50)
    print("One Pod Per Node Constraint Test")
    print("=" * 50)
    
    # Clean up all existing test pods
    print("Cleaning up existing test pods...")
    cleaned_count = 0
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        for pod in pods.items:
            if (pod.metadata.name.startswith(('test-', 'simple-', 'multi-')) and 
                pod.spec.scheduler_name == scheduler_name):
                v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)
                print(f"  Deleted: {pod.metadata.name}")
                cleaned_count += 1
        
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} existing pods")
            time.sleep(8)  # Wait longer for cleanup
        else:
            print("No existing test pods to clean up")
            
    except ApiException as e:
        print(f"Warning: Error during cleanup: {e}")
    
    # Create 4 test pods (more than the 3 nodes we have)
    pod_names = ["multi-test-pod-1", "multi-test-pod-2", "multi-test-pod-3", "multi-test-pod-4"]
    
    print(f"\nCreating {len(pod_names)} pods...")
    for pod_name in pod_names:
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name
            },
            "spec": {
                "schedulerName": scheduler_name,
                "containers": [{
                    "name": "test-container",
                    "image": "busybox:latest",
                    "command": ["sleep", "600"],
                    "resources": {
                        "requests": {
                            "memory": "32Mi",
                            "cpu": "25m"
                        }
                    }
                }]
            }
        }
        
        try:
            v1.create_namespaced_pod(namespace=namespace, body=pod_manifest)
            print(f"  Created: {pod_name}")
            time.sleep(1)  # Small delay between pod creations
        except ApiException as e:
            print(f"  Failed to create {pod_name}: {e}")
            return False
    
    # Wait for scheduling to complete
    print("\nWaiting for pods to be scheduled...")
    time.sleep(15)
    
    # Check final pod placement
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        scheduled_pods = []
        pending_pods = []
        
        for pod in pods.items:
            if pod.metadata.name.startswith('multi-test-pod'):
                if pod.spec.node_name:
                    scheduled_pods.append({
                        'name': pod.metadata.name,
                        'node': pod.spec.node_name,
                        'status': pod.status.phase
                    })
                else:
                    pending_pods.append({
                        'name': pod.metadata.name,
                        'status': pod.status.phase
                    })
    
        print(f"\nScheduled pods: {len(scheduled_pods)}")
        print(f"Pending pods: {len(pending_pods)}")
        
        # Show scheduled pods
        if scheduled_pods:
            print("\nScheduled pods:")
            for pod in scheduled_pods:
                print(f"  {pod['name']} -> {pod['node']} (status: {pod['status']})")
        
        # Show pending pods
        if pending_pods:
            print("\nPending pods:")
            for pod in pending_pods:
                print(f"  {pod['name']} (status: {pod['status']})")
        
        # Check one-pod-per-node constraint
        node_counts = {}
        for pod in scheduled_pods:
            node = pod['node']
            node_counts[node] = node_counts.get(node, 0) + 1
        
        print(f"\nNode assignments:")
        constraint_violated = False
        for node, count in node_counts.items():
            print(f"  {node}: {count} pod(s)")
            if count > 1:
                constraint_violated = True
                print(f"    ⚠️  CONSTRAINT VIOLATION: Node has {count} pods (should be max 1)")
        
        # We have 3 nodes, so should schedule max 3 pods
        expected_scheduled = min(len(pod_names), 3)
        expected_pending = max(0, len(pod_names) - 3)
        
        success = True
        
        # Check if constraint is respected
        if constraint_violated:
            print(f"\n✗ CONSTRAINT VIOLATION: Some nodes have multiple pods")
            success = False
        else:
            print(f"\n✓ One-pod-per-node constraint respected")
        
        # Check expected scheduling counts
        if len(scheduled_pods) != expected_scheduled:
            print(f"✗ Expected {expected_scheduled} scheduled pods, got {len(scheduled_pods)}")
            success = False
        else:
            print(f"✓ Expected number of pods scheduled: {len(scheduled_pods)}")
        
        if len(pending_pods) != expected_pending:
            print(f"✗ Expected {expected_pending} pending pods, got {len(pending_pods)}")
            success = False
        else:
            print(f"✓ Expected number of pods pending: {len(pending_pods)}")
        
        return success
        
    except ApiException as e:
        print(f"✗ Error checking pod status: {e}")
        return False


if __name__ == "__main__":
    print("Starting multi-pod scheduler test...\n")
    
    # Check scheduler health first
    if not check_scheduler_health():
        print("Scheduler is not healthy, exiting...")
        sys.exit(1)
    
    print()
    
    # Run the multi-pod constraint test
    success = test_one_pod_per_node()
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    if success:
        print("✓ One-pod-per-node constraint: PASSED")
        print("\n🎉 TEST PASSED")
        sys.exit(0)
    else:
        print("✗ One-pod-per-node constraint: FAILED")
        print("\n❌ TEST FAILED")
        sys.exit(1)