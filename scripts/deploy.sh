#!/bin/bash

# Local deployment script for testing the CI/CD pipeline
# This script mimics what GitHub Actions does

set -e

# Configuration
DROPLET_IP="${DROPLET_IP:-64.227.134.87}"  # Replace with your droplet IP
DROPLET_USER="root"
SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/id_rsa}"  # Path to your SSH key

echo "🚀 Starting local deployment to k3s..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Check if required tools are available
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v ssh &> /dev/null; then
        print_error "SSH is not installed"
        exit 1
    fi
    
    if [ ! -f "$SSH_KEY_PATH" ]; then
        print_error "SSH key not found at $SSH_KEY_PATH"
        exit 1
    fi
    
    print_status "Requirements check passed"
}

# Build Docker image
build_image() {
    print_status "Building Docker image for x86_64..."
    docker build --platform linux/amd64 -t football-transfers-app:latest .
    
    print_status "Saving Docker image..."
    docker save football-transfers-app:latest -o football-transfers-app.tar
    ls -la football-transfers-app.tar
}

# Deploy to droplet
deploy_to_droplet() {
    print_status "Copying image to droplet..."
    scp -i "$SSH_KEY_PATH" football-transfers-app.tar $DROPLET_USER@$DROPLET_IP:/tmp/
    
    print_status "Copying Kubernetes manifests..."
    scp -i "$SSH_KEY_PATH" -r k8s/ $DROPLET_USER@$DROPLET_IP:/tmp/
    
    print_status "Deploying to k3s..."
    ssh -i "$SSH_KEY_PATH" $DROPLET_USER@$DROPLET_IP << 'EOF'
        set -e
        echo "🧹 Cleaning up old image..."
        sudo k3s ctr images rm docker.io/library/football-transfers-app:latest || true
        
        echo "📦 Loading new image into k3s..."
        sudo k3s ctr images import /tmp/football-transfers-app.tar
        
        echo "🔍 Verifying image is loaded..."
        sudo k3s ctr images ls | grep football-transfers-app
        
        echo "📋 Applying Kubernetes manifests..."
        sudo kubectl apply -f /tmp/k8s/namespace.yaml
        sudo kubectl apply -f /tmp/k8s/deployment.yaml
        sudo kubectl apply -f /tmp/k8s/service.yaml
        
        echo "🔄 Rolling out deployment..."
        sudo kubectl rollout restart deployment/football-transfers-app -n football-transfers
        
        echo "⏳ Waiting for deployment to be ready..."
        sudo kubectl rollout status deployment/football-transfers-app -n football-transfers --timeout=300s
        
        echo "✅ Deployment completed successfully!"
        echo "📊 Current pod status:"
        sudo kubectl get pods -n football-transfers
        
        echo "🌐 Service status:"
        sudo kubectl get svc -n football-transfers
EOF
}

# Health check
health_check() {
    print_status "Waiting for app to be ready..."
    sleep 30
    
    print_status "Running health check..."
    for i in {1..10}; do
        if curl -f http://$DROPLET_IP:30080/health; then
            print_status "✅ Health check passed!"
            break
        else
            print_warning "Health check failed, retrying in 10 seconds... (attempt $i/10)"
            sleep 10
        fi
    done
}

# Run tests
run_tests() {
    print_status "Running integration tests..."
    python test_app.py http://$DROPLET_IP:30080
}

# Cleanup
cleanup() {
    print_status "Cleaning up..."
    ssh -i "$SSH_KEY_PATH" $DROPLET_USER@$DROPLET_IP << 'EOF'
        echo "🧹 Cleaning up temporary files..."
        rm -f /tmp/football-transfers-app.tar
        rm -rf /tmp/k8s/
EOF
    
    rm -f football-transfers-app.tar
}

# Main execution
main() {
    check_requirements
    build_image
    deploy_to_droplet
    health_check
    run_tests
    cleanup
    
    print_status "🎉 Deployment completed successfully!"
    print_status "🌐 Your app is available at: http://$DROPLET_IP:30080"
    print_status "📚 API docs: http://$DROPLET_IP:30080/docs"
}

# Handle script interruption
trap cleanup EXIT

# Run main function
main "$@" 