#!/bin/bash

# Football Transfers App Kubernetes Deployment Script
# Run this script to deploy your FastAPI app to k3s

set -e

echo "🚀 Starting Football Transfers App Kubernetes Deployment..."

# Configuration
DOCKER_USERNAME="your-dockerhub-username"  # Replace with your Docker Hub username
IMAGE_NAME="football-transfers-app"
TAG="latest"
FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:$TAG"

echo "📦 Building Docker image..."
docker build -t $IMAGE_NAME:$TAG .

echo "🏷️  Tagging image for registry..."
docker tag $IMAGE_NAME:$TAG $FULL_IMAGE_NAME

echo "📤 Pushing image to Docker Hub..."
echo "Please make sure you're logged in to Docker Hub: docker login"
docker push $FULL_IMAGE_NAME

echo "🧹 Cleaning up test namespace..."
kubectl delete namespace test-k3s --ignore-not-found=true

echo "📋 Applying Kubernetes manifests..."
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

echo "⏳ Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/football-transfers-app -n football-transfers

echo "🔍 Checking deployment status..."
kubectl get pods -n football-transfers
kubectl get svc -n football-transfers

echo "🌐 Getting service information..."
NODEPORT=$(kubectl get svc football-transfers-service -n football-transfers -o jsonpath='{.spec.ports[0].nodePort}')
echo "Your app is accessible at: http://YOUR_DROPLET_IP:$NODEPORT"
echo "Health check: http://YOUR_DROPLET_IP:$NODEPORT/health"

echo "✅ Deployment complete!"
echo "📊 To monitor logs: kubectl logs -f deployment/football-transfers-app -n football-transfers"
echo "🔧 To scale: kubectl scale deployment football-transfers-app --replicas=2 -n football-transfers" 