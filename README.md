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

4. **Run simple test:**
   ```bash
   python3 test/simple_test.py
   ```

