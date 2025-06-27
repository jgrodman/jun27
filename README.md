# Custom Kubernetes Scheduler

## Prerequisites

- Kubernetes cluster (tested with minikube)
- Docker
- kubectl configured to access your cluster
- Python 3.11+ (for running tests)

## Quick Start

1. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Set up minikube cluster with multiple nodes:**
   ```bash
    minikube start --driver=docker --nodes=3 --memory=2048 --cpus=2
   ```

3. **Deploy the scheduler:**
   ```bash
   ./deploy_scheduler.sh
   ```

4. **Run tests in order:**

   **Basic scheduling test:**
   ```bash
   python3 test/simple_test.py
   ```

   **One-pod-per-node constraint test:**
   ```bash
   python3 test/one_pod_per_node.py
   ```

   **Priority and preemption test:**
   ```bash
   python3 test/priorities.py
   ```

## Features

- **One-pod-per-node constraint**: Ensures no node runs more than one pod from our scheduler
- **Priority-based scheduling**: Uses `scheduler.priority` annotation to determine pod priority
- **Preemption**: Higher priority pods can preempt lower priority ones when no nodes are available
- **Lowest priority selection**: Always preempts the lowest priority pod when multiple candidates exist

## Next steps

- **Gang-scheduling**: Schedule all pods in a job together or none at all
- **Configurable namespaces**: Support custom namespaces (currently uses 'scheduling' and 'default')