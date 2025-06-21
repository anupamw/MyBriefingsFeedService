#!/bin/bash

# DigitalOcean FastAPI App Deployment Script
# Run this script on your DigitalOcean droplet to set up the environment

set -e  # Exit on any error

echo "🚀 Setting up FastAPI app on DigitalOcean..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip
echo "🐍 Installing Python and pip..."
sudo apt install -y python3 python3-pip python3-venv git curl

# Create application directory
echo "📁 Creating application directory..."
sudo mkdir -p /var/www/fastapi-app
sudo chown $USER:$USER /var/www/fastapi-app

# Clone repository (if not already done)
if [ ! -d "/var/www/fastapi-app/.git" ]; then
    echo "📥 Cloning repository..."
    cd /var/www/fastapi-app
    git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git .
else
    echo "📥 Repository already exists, pulling latest changes..."
    cd /var/www/fastapi-app
    git pull origin main
fi

# Create virtual environment
echo "🔧 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up systemd service
echo "⚙️ Setting up systemd service..."
sudo cp fastapi-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fastapi-app
sudo systemctl start fastapi-app

# Check service status
echo "🔍 Checking service status..."
sudo systemctl status fastapi-app --no-pager

# Test the application
echo "🧪 Testing application..."
sleep 3
if curl -f http://localhost:8000/health; then
    echo "✅ Application is running successfully!"
    echo "🌐 Your FastAPI app is available at: http://YOUR_DROPLET_IP:8000"
    echo "📚 API documentation: http://YOUR_DROPLET_IP:8000/docs"
else
    echo "❌ Application failed to start. Check logs with: sudo journalctl -u fastapi-app -f"
    exit 1
fi

echo "🎉 Deployment completed successfully!" 