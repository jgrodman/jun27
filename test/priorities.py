#!/usr/bin/env python3
"""
Priority and preemption test for the custom Kubernetes scheduler

Test: Create 3 pods (2 high priority, 1 low priority) on 3 nodes, 
then add another high priority pod and verify it preempts the low priority one
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


def test_priority_preemption():
    """Test that higher priority pods preempt lower priority ones"""
    
    # Set up Kubernetes client
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    
    v1 = client.CoreV1Api()
    namespace = "default"
    scheduler_name = "custom-scheduler"
    
    print("=" * 60)
    print("Priority and Preemption Test")
    print("=" * 60)
    
    # Clean up all existing test pods
    print("Cleaning up existing test pods...")
    cleaned_count = 0
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        for pod in pods.items:
            if (pod.metadata.name.startswith(('priority-', 'test-', 'simple-', 'multi-')) and 
                pod.spec.scheduler_name == scheduler_name):
                v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)
                print(f"  Deleted: {pod.metadata.name}")
                cleaned_count += 1
        
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} existing pods")
            print("Waiting for pods to be fully deleted...")
            time.sleep(10)  # Wait longer for cleanup
            
            # Verify pods are actually deleted
            for i in range(60):  # Wait up to 60 more seconds
                remaining_pods = v1.list_namespaced_pod(namespace=namespace)
                test_pods_remaining = [p for p in remaining_pods.items 
                                     if p.metadata.name.startswith(('priority-', 'test-', 'simple-', 'multi-')) and 
                                        p.spec.scheduler_name == scheduler_name]
                if not test_pods_remaining:
                    print("✓ All test pods deleted")
                    break
                print(f"  Still waiting for {len(test_pods_remaining)} pods to delete...")
                time.sleep(1)
        else:
            print("No existing test pods to clean up")
            
    except ApiException as e:
        print(f"Warning: Error during cleanup: {e}")
    
    # Phase 1: Create 3 initial pods (2 high priority, 1 low priority)
    initial_pods = [
        {"name": "priority-high-1", "priority": 80},
        {"name": "priority-high-2", "priority": 80}, 
        {"name": "priority-low-1", "priority": 20}
    ]
    
    print(f"\nPhase 1: Creating {len(initial_pods)} initial pods...")
    for pod_info in initial_pods:
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_info["name"],
                "annotations": {
                    "scheduler.priority": str(pod_info["priority"])
                }
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
            print(f"  Created: {pod_info['name']} (priority: {pod_info['priority']})")
            time.sleep(2)  # Delay between pod creations
        except ApiException as e:
            print(f"  Failed to create {pod_info['name']}: {e}")
            return False
    
    # Wait for initial pods to be scheduled and running
    print("\nWaiting for initial pods to be scheduled and running...")
    for i in range(60):  # Check for up to 60 seconds
        try:
            pods = v1.list_namespaced_pod(namespace=namespace)
            scheduled_count = sum(1 for pod in pods.items 
                                if pod.metadata.name.startswith('priority-') and 
                                   pod.spec.node_name and 
                                   pod.status.phase == "Running")
            print(f"  {scheduled_count}/3 pods running...")
            if scheduled_count == 3:
                print("✓ All initial pods are running")
                break
        except ApiException:
            pass
        time.sleep(1)
    else:
        print("✗ Timeout: Initial pods did not start running within 60 seconds")
        return False
    
    # Check initial pod placement
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        initial_scheduled_pods = []
        
        for pod in pods.items:
            if pod.metadata.name.startswith('priority-') and pod.spec.node_name:
                initial_scheduled_pods.append({
                    'name': pod.metadata.name,
                    'node': pod.spec.node_name,
                    'status': pod.status.phase,
                    'priority': pod.metadata.annotations.get('scheduler.priority', 'unknown')
                })
        
        print(f"\nInitial scheduled pods: {len(initial_scheduled_pods)}")
        for pod in initial_scheduled_pods:
            print(f"  {pod['name']} -> {pod['node']} (priority: {pod['priority']}, status: {pod['status']})")
        
        if len(initial_scheduled_pods) != 3:
            print(f"✗ Expected 3 initial pods scheduled, got {len(initial_scheduled_pods)}")
            return False
            
        # Check that all 3 nodes are occupied (one pod per node)
        nodes_used = set(pod['node'] for pod in initial_scheduled_pods)
        if len(nodes_used) != 3:
            print(f"✗ Expected 3 nodes to be used, got {len(nodes_used)}: {nodes_used}")
            return False
            
        print("✓ All 3 initial pods scheduled to different nodes")
        
    except ApiException as e:
        print(f"✗ Error checking initial pod status: {e}")
        return False
    
    # Phase 2: Create a new high priority pod that should trigger preemption
    print(f"\nPhase 2: Creating high priority pod that should trigger preemption...")
    preempting_pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "priority-preemptor",
            "annotations": {
                "scheduler.priority": "90"  # Higher than existing pods
            }
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
        v1.create_namespaced_pod(namespace=namespace, body=preempting_pod)
        print(f"  Created: priority-preemptor (priority: 90)")
    except ApiException as e:
        print(f"  Failed to create priority-preemptor: {e}")
        return False
    
    # Wait for preemption to occur
    print("\nWaiting for preemption to complete...")
    for i in range(60):  # Check for up to 60 seconds
        try:
            pods = v1.list_namespaced_pod(namespace=namespace)
            preemptor_running = any(pod.metadata.name == 'priority-preemptor' and 
                                  pod.spec.node_name and 
                                  pod.status.phase == "Running"
                                  for pod in pods.items)
            low_priority_gone = not any(pod.metadata.name == 'priority-low-1' and 
                                      pod.spec.node_name
                                      for pod in pods.items)
            
            print(f"  Preemptor running: {preemptor_running}, Low priority gone: {low_priority_gone}")
            if preemptor_running and low_priority_gone:
                print("✓ Preemption completed")
                break
        except ApiException:
            pass
        time.sleep(1)
    else:
        print("✗ Timeout: Preemption did not complete within 60 seconds")
        return False
    
    # Check final pod placement
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        final_scheduled_pods = []
        final_pending_pods = []
        
        for pod in pods.items:
            if pod.metadata.name.startswith('priority-'):
                if pod.spec.node_name:
                    final_scheduled_pods.append({
                        'name': pod.metadata.name,
                        'node': pod.spec.node_name,
                        'status': pod.status.phase,
                        'priority': pod.metadata.annotations.get('scheduler.priority', 'unknown')
                    })
                else:
                    final_pending_pods.append({
                        'name': pod.metadata.name,
                        'status': pod.status.phase,
                        'priority': pod.metadata.annotations.get('scheduler.priority', 'unknown')
                    })
        
        print(f"\nFinal scheduled pods: {len(final_scheduled_pods)}")
        for pod in final_scheduled_pods:
            print(f"  {pod['name']} -> {pod['node']} (priority: {pod['priority']}, status: {pod['status']})")
        
        print(f"\nFinal pending/terminating pods: {len(final_pending_pods)}")
        for pod in final_pending_pods:
            print(f"  {pod['name']} (priority: {pod['priority']}, status: {pod['status']})")
        
        # Validate preemption occurred correctly
        success = True
        
        # Check that priority-preemptor (priority 90) is scheduled
        preemptor_scheduled = any(pod['name'] == 'priority-preemptor' for pod in final_scheduled_pods)
        if not preemptor_scheduled:
            print("✗ High priority preemptor pod was not scheduled")
            success = False
        else:
            print("✓ High priority preemptor pod is scheduled")
        
        # Check that low priority pod (priority 20) is no longer scheduled
        low_priority_scheduled = any(pod['name'] == 'priority-low-1' for pod in final_scheduled_pods)
        if low_priority_scheduled:
            print("✗ Low priority pod was not preempted")
            success = False
        else:
            print("✓ Low priority pod was preempted")
        
        # Check that we still have exactly 3 scheduled pods (constraint maintained)
        if len(final_scheduled_pods) != 3:
            print(f"✗ Expected 3 scheduled pods after preemption, got {len(final_scheduled_pods)}")
            success = False
        else:
            print("✓ One-pod-per-node constraint maintained after preemption")
        
        # Check that all scheduled pods have high priority (80 or 90)
        high_priority_count = sum(1 for pod in final_scheduled_pods 
                                if int(pod['priority']) >= 80)
        if high_priority_count != 3:
            print(f"✗ Expected 3 high priority pods scheduled, got {high_priority_count}")
            success = False
        else:
            print("✓ All scheduled pods have high priority")
        
        return success
        
    except ApiException as e:
        print(f"✗ Error checking final pod status: {e}")
        return False


if __name__ == "__main__":
    print("Starting priority and preemption test...\n")
    
    # Check scheduler health first
    if not check_scheduler_health():
        print("Scheduler is not healthy, exiting...")
        sys.exit(1)
    
    print()
    
    # Run the preemption test
    success = test_priority_preemption()
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    if success:
        print("✓ Priority and preemption: PASSED")
        print("\n🎉 TEST PASSED")
        sys.exit(0)
    else:
        print("✗ Priority and preemption: FAILED")
        print("\n❌ TEST FAILED")
        sys.exit(1)