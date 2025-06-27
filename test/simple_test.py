#!/usr/bin/env python3
"""
Simple test for the custom Kubernetes scheduler

Test: Create a single pod and verify it gets scheduled
"""

import time
import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException


def test_single_pod_scheduling():
    """Test that a single pod gets scheduled by our custom scheduler"""
    
    # Set up Kubernetes client
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    
    v1 = client.CoreV1Api()
    namespace = "default"
    scheduler_name = "custom-scheduler"
    pod_name = "simple-test-pod"
    
    print("=" * 50)
    print("Simple Scheduler Test")
    print("=" * 50)
    
    # Clean up all existing test pods
    print("Cleaning up existing test pods...")
    cleaned_count = 0
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        for pod in pods.items:
            if (pod.metadata.name.startswith(('test-', 'simple-')) and 
                pod.spec.scheduler_name == scheduler_name):
                v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)
                print(f"  Deleted: {pod.metadata.name}")
                cleaned_count += 1
        
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} existing pods")
            time.sleep(5)  # Wait for deletion
        else:
            print("No existing test pods to clean up")
            
    except ApiException as e:
        print(f"Warning: Error during cleanup: {e}")
    
    # Create test pod
    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "annotations": {
                "scheduler.priority": "50"
            }
        },
        "spec": {
            "schedulerName": scheduler_name,
            "containers": [{
                "name": "test-container",
                "image": "busybox:latest",
                "command": ["sleep", "300"],
                "resources": {
                    "requests": {
                        "memory": "32Mi",
                        "cpu": "25m"
                    }
                }
            }]
        }
    }
    
    print(f"Creating pod: {pod_name}")
    try:
        v1.create_namespaced_pod(namespace=namespace, body=pod_manifest)
        print("✓ Pod created successfully")
    except ApiException as e:
        print(f"✗ Failed to create pod: {e}")
        return False
    
    # Wait for pod to be scheduled
    print("Waiting for pod to be scheduled...")
    max_wait = 30  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            
            if pod.spec.node_name:
                print(f"✓ Pod scheduled to node: {pod.spec.node_name}")
                print(f"✓ Pod status: {pod.status.phase}")
                
                # Get pod details
                pod_details = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                print(f"✓ Pod IP: {pod_details.status.pod_ip}")
                
                return True
                
            time.sleep(2)
            
        except ApiException as e:
            print(f"✗ Error reading pod: {e}")
            return False
    
    print(f"✗ Pod was not scheduled within {max_wait} seconds")
    
    # Show pod status for debugging
    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        print(f"Final pod status: {pod.status.phase}")
        if pod.status.conditions:
            for condition in pod.status.conditions:
                print(f"  {condition.type}: {condition.status} - {condition.reason}")
    except:
        pass
    
    return False


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


if __name__ == "__main__":
    print("Starting simple scheduler test...\n")
    
    # Check scheduler health first
    if not check_scheduler_health():
        print("Scheduler is not healthy, exiting...")
        sys.exit(1)
    
    print()
    
    # Run the test
    success = test_single_pod_scheduling()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ TEST PASSED: Pod was successfully scheduled")
        sys.exit(0)
    else:
        print("✗ TEST FAILED: Pod was not scheduled")
        sys.exit(1)