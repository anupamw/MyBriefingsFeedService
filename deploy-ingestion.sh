#!/bin/bash

# Feed Ingestion Service Deployment Script
# This script deploys the feed ingestion service to k3s

set -e

echo "🚀 Deploying Feed Ingestion Service to k3s..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="briefings-feed"
SERVICE_NAME="feed-ingestion"
REGISTRY="localhost:5000"  # Change this to your registry

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Check if k3s is running
if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to k3s cluster. Is k3s running?"
    exit 1
fi

print_status "Connected to k3s cluster"

# Create namespace if it doesn't exist
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    print_status "Creating namespace: $NAMESPACE"
    kubectl apply -f k8s/namespace.yaml
else
    print_status "Namespace $NAMESPACE already exists"
fi

# Build and push the Docker image
print_status "Building feed ingestion Docker image..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

# Build the image
cd services/feed-ingestion
docker build -t $SERVICE_NAME:latest .
cd ../..

# Tag and push to registry (if using remote registry)
# docker tag $SERVICE_NAME:latest $REGISTRY/$SERVICE_NAME:latest
# docker push $REGISTRY/$SERVICE_NAME:latest

print_status "Docker image built successfully"

# Create secrets (you need to update these with your actual API keys)
print_warning "Please update k8s/secrets/api-keys.yaml with your actual API keys before proceeding"
read -p "Have you updated the API keys? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_error "Please update the API keys first"
    exit 1
fi

# Apply secrets
print_status "Applying API keys secret..."
kubectl apply -f k8s/secrets/api-keys.yaml

# Apply storage
print_status "Creating persistent volumes..."
kubectl apply -f k8s/storage/persistent-volumes.yaml

# Deploy Redis
print_status "Deploying Redis..."
kubectl apply -f k8s/redis/deployment.yaml
kubectl apply -f k8s/redis/service.yaml

# Wait for Redis to be ready
print_status "Waiting for Redis to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/redis -n $NAMESPACE

# Deploy the feed ingestion service
print_status "Deploying feed ingestion service..."
kubectl apply -f k8s/feed-ingestion/deployment.yaml
kubectl apply -f k8s/feed-ingestion/service.yaml

# Wait for the deployment to be ready
print_status "Waiting for feed ingestion service to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/$SERVICE_NAME -n $NAMESPACE

# Check service status
print_status "Checking service status..."
kubectl get pods -n $NAMESPACE -l app=$SERVICE_NAME

# Get service information
print_status "Service information:"
kubectl get service -n $NAMESPACE

# Test the service
print_status "Testing service health..."
SERVICE_IP=$(kubectl get service feed-ingestion-service -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
SERVICE_PORT=$(kubectl get service feed-ingestion-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].port}')

if [ ! -z "$SERVICE_IP" ]; then
    print_status "Service is available at: $SERVICE_IP:$SERVICE_PORT"
    print_status "You can test it with: kubectl port-forward service/feed-ingestion-service 8001:8001 -n $NAMESPACE"
else
    print_error "Could not get service IP"
fi

# Show logs
print_status "Recent logs from feed ingestion service:"
kubectl logs deployment/$SERVICE_NAME -c feed-ingestion-api -n $NAMESPACE --tail=10

print_status "Recent logs from Celery worker:"
kubectl logs deployment/$SERVICE_NAME -c celery-worker -n $NAMESPACE --tail=10

print_status "Recent logs from Celery beat:"
kubectl logs deployment/$SERVICE_NAME -c celery-beat -n $NAMESPACE --tail=10

print_status "✅ Feed Ingestion Service deployed successfully!"

echo
echo "📋 Next steps:"
echo "1. Test the API: kubectl port-forward service/feed-ingestion-service 8001:8001 -n $NAMESPACE"
echo "2. Check health: curl http://localhost:8001/health"
echo "3. View data sources: curl http://localhost:8001/data-sources"
echo "4. Trigger ingestion: curl -X POST http://localhost:8001/ingest/perplexity"
echo "5. Monitor logs: kubectl logs -f deployment/$SERVICE_NAME -n $NAMESPACE"
echo
echo "🔧 Useful commands:"
echo "  - View all pods: kubectl get pods -n $NAMESPACE"
echo "  - View services: kubectl get services -n $NAMESPACE"
echo "  - View logs: kubectl logs deployment/$SERVICE_NAME -n $NAMESPACE"
echo "  - Delete deployment: kubectl delete deployment/$SERVICE_NAME -n $NAMESPACE" 