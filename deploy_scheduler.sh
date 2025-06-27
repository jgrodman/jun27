#!/bin/bash

# Custom Kubernetes Scheduler Deployment Script

set -e

NAMESPACE="scheduling"
SCHEDULER_NAME="custom-scheduler"
IMAGE_NAME="custom-scheduler:latest"

echo "==========================================="
echo "Custom Kubernetes Scheduler Deployment"
echo "==========================================="
echo "Namespace: $NAMESPACE" 
echo "Scheduler Name: $SCHEDULER_NAME"
echo "Image: $IMAGE_NAME"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."

if ! command_exists kubectl; then
    echo "Error: kubectl is not installed or not in PATH"
    exit 1
fi

if ! command_exists docker; then
    echo "Error: docker is not installed or not in PATH"
    exit 1
fi

# Check if kubectl can connect to cluster
if ! kubectl cluster-info >/dev/null 2>&1; then
    echo "Error: Cannot connect to Kubernetes cluster"
    echo "Please ensure kubectl is configured properly"
    exit 1
fi

echo "✓ Prerequisites check passed"
echo ""

# Build the scheduler Docker image
echo "Building scheduler Docker image..."
docker build -t $IMAGE_NAME .

# For minikube, load the image into minikube's Docker daemon
if kubectl config current-context | grep -q minikube; then
    echo "Detected minikube cluster, loading image..."
    minikube image load $IMAGE_NAME
fi

echo "✓ Docker image built and loaded"
echo ""

# Create scheduling namespace
echo "Creating namespace $NAMESPACE..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo "✓ Namespace created/verified"
echo ""

# Deploy the scheduler
echo "Deploying custom scheduler..."

kubectl apply -f scheduler-deployment.yaml

echo "✓ Scheduler deployed"
echo ""

# Wait for deployment to be ready
echo "Waiting for scheduler deployment to be ready..."
kubectl rollout status deployment/custom-scheduler -n $NAMESPACE --timeout=120s

echo "✓ Scheduler deployment is ready"
echo ""

# Verify the scheduler is running
echo "Verifying scheduler status..."
SCHEDULER_POD=$(kubectl get pods -n $NAMESPACE -l app=custom-scheduler -o jsonpath='{.items[0].metadata.name}')

if [ -n "$SCHEDULER_POD" ]; then
    echo "Scheduler pod: $SCHEDULER_POD"
    kubectl get pod $SCHEDULER_POD -n $NAMESPACE
    echo ""
    
    echo "Scheduler logs (last 10 lines):"
    kubectl logs $SCHEDULER_POD -n $NAMESPACE --tail=10
else
    echo "Warning: Could not find scheduler pod"
fi
