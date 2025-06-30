#!/bin/bash

# My Briefings App Kubernetes Deployment Script (Local Image)
# This script loads the image directly into k3s without needing a registry

set -e

echo "🚀 Starting My Briefings App Kubernetes Deployment (Local Image)..."

# Configuration
IMAGE_NAME="my-briefings-app"
TAG="latest"
IMAGE_TAR="my-briefings-app.tar"

echo "📦 Building Docker image..."
docker build -t $IMAGE_NAME:$TAG .

echo "💾 Saving image to tar file..."
docker save $IMAGE_NAME:$TAG -o $IMAGE_TAR

echo "📤 Copying image to droplet..."
echo "Please copy the image file to your droplet:"
echo "scp $IMAGE_TAR root@YOUR_DROPLET_IP:/tmp/"

echo "📋 Applying Kubernetes manifests..."
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

echo "⏳ Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/my-briefings-app -n my-briefings

echo "🔍 Checking deployment status..."
kubectl get pods -n my-briefings
kubectl get svc -n my-briefings

echo "🌐 Getting service information..."
NODEPORT=$(kubectl get svc my-briefings-service -n my-briefings -o jsonpath='{.spec.ports[0].nodePort}')
echo "Your app is accessible at: http://YOUR_DROPLET_IP:$NODEPORT"
echo "Health check: http://YOUR_DROPLET_IP:$NODEPORT/health"

echo "✅ Deployment complete!"
echo "📊 To monitor logs: kubectl logs -f deployment/my-briefings-app -n my-briefings"
echo "🔧 To scale: kubectl scale deployment my-briefings-app --replicas=2 -n my-briefings" 