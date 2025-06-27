# Custom Kubernetes Scheduler

## Prerequisites

- Kubernetes cluster (tested with minikube)
- Docker
- kubectl configured to access your cluster
- Python 3.11+ (for running tests)

## Quick Start

1. **Set up minikube cluster with multiple nodes:**
   ```bash
    minikube start --driver=docker --nodes=3 --memory=2048 --cpus=2
   ```

2. **Deploy the scheduler:**
   ```bash
   ./deploy_scheduler.sh
   ```

3. **Deploy a pod:**
   ```bash
   kubectl apply -f test/single-pod.yaml
   ```
