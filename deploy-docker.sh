#!/bin/bash

# DigitalOcean FastAPI Docker App Deployment Script
# Run this script on your DigitalOcean droplet to set up the Docker environment

set -e  # Exit on any error

echo "🐳 Setting up FastAPI Docker app on DigitalOcean..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
echo "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installed successfully"
else
    echo "✅ Docker is already installed"
fi

# Install Docker Compose
echo "🐙 Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed successfully"
else
    echo "✅ Docker Compose is already installed"
fi

# Create application directory
echo "📁 Creating application directory..."
sudo mkdir -p /var/www/my-briefings-app
sudo chown $USER:$USER /var/www/my-briefings-app

# Clone repository (if not already done)
if [ ! -d "/var/www/my-briefings-app/.git" ]; then
    echo "📥 Cloning repository..."
    cd /var/www/my-briefings-app
    git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git .
else
    echo "📥 Repository already exists, pulling latest changes..."
    cd /var/www/my-briefings-app
    git pull origin main
fi

# Build and run Docker container
echo "🐳 Building Docker image..."
docker build -t my-briefings-app:latest .

# Stop existing container if running
echo "🛑 Stopping existing container..."
docker stop my-briefings-app || true
docker rm my-briefings-app || true

# Run new container
echo "🚀 Starting Docker container..."
docker run -d \
    --name my-briefings-app \
    --restart unless-stopped \
    -p 8000:8000 \
    -e PYTHONPATH=/app \
    my-briefings-app:latest

# Wait for container to be ready
echo "⏳ Waiting for container to be ready..."
sleep 10

# Check container status
echo "🔍 Checking container status..."
docker ps | grep my-briefings-app

# Test the application
echo "🧪 Testing application..."
if curl -f http://localhost:8000/health; then
    echo "✅ Application is running successfully!"
    echo "🌐 Your FastAPI app is available at: http://$(curl -s ifconfig.me):8000"
    echo "📚 API documentation: http://$(curl -s ifconfig.me):8000/docs"
else
    echo "❌ Application failed to start. Check logs with: docker logs my-briefings-app"
    docker logs my-briefings-app
    exit 1
fi

# Clean up old images
echo "🧹 Cleaning up old Docker images..."
docker image prune -f

echo "🎉 Docker deployment completed successfully!"

# Show useful commands
echo ""
echo "📋 Useful commands:"
echo "  View logs: docker logs my-briefings-app"
echo "  Restart: docker restart my-briefings-app"
echo "  Stop: docker stop my-briefings-app"
echo "  Remove: docker rm my-briefings-app"
echo "  Shell access: docker exec -it my-briefings-app /bin/bash" 