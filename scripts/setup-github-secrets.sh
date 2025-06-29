#!/bin/bash

# Helper script to set up GitHub secrets for CI/CD pipeline

echo "🔧 GitHub Secrets Setup Helper"
echo "=============================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Get droplet IP
echo "Enter your droplet IP address:"
read -p "DROPLET_IP: " DROPLET_IP

# Validate IP format
if [[ ! $DROPLET_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_warning "Invalid IP address format. Please enter a valid IP address."
    exit 1
fi

print_info "Droplet IP: $DROPLET_IP"

# Check for SSH key
SSH_KEY_PATH="${SSH_KEY_PATH:-~/.ssh/id_rsa}"

if [ ! -f "$SSH_KEY_PATH" ]; then
    print_warning "SSH key not found at $SSH_KEY_PATH"
    echo "Please enter the path to your SSH private key:"
    read -p "SSH_KEY_PATH: " SSH_KEY_PATH
    
    if [ ! -f "$SSH_KEY_PATH" ]; then
        print_warning "SSH key not found. Please generate one first:"
        echo "ssh-keygen -t rsa -b 4096 -C \"your-email@example.com\""
        exit 1
    fi
fi

print_info "SSH Key Path: $SSH_KEY_PATH"

# Display the secrets to add
echo ""
echo "📋 Add these secrets to your GitHub repository:"
echo "================================================"
echo ""
echo "1. Go to your GitHub repository"
echo "2. Click Settings → Secrets and variables → Actions"
echo "3. Click 'New repository secret'"
echo "4. Add the following secrets:"
echo ""

echo "Secret Name: DROPLET_IP"
echo "Secret Value: $DROPLET_IP"
echo ""

echo "Secret Name: SSH_PRIVATE_KEY"
echo "Secret Value: (Copy the entire content of your private key file)"
echo ""

# Show the private key content
print_info "Your SSH private key content:"
echo "----------------------------------------"
cat "$SSH_KEY_PATH"
echo "----------------------------------------"
echo ""

print_warning "⚠️  IMPORTANT: Keep your private key secure and never share it publicly!"
echo ""

# Test SSH connection
print_info "Testing SSH connection to your droplet..."
if ssh -i "$SSH_KEY_PATH" -o ConnectTimeout=10 -o BatchMode=yes root@$DROPLET_IP "echo 'SSH connection successful'" 2>/dev/null; then
    print_success "SSH connection test passed!"
else
    print_warning "SSH connection test failed. Please ensure:"
    echo "1. Your SSH key is added to the droplet"
    echo "2. The droplet IP is correct"
    echo "3. The droplet is accessible"
    echo ""
    echo "To add your SSH key to the droplet:"
    echo "ssh-copy-id -i $SSH_KEY_PATH root@$DROPLET_IP"
fi

echo ""
print_info "Next steps:"
echo "1. Add the secrets to your GitHub repository"
echo "2. Push your code to the main branch"
echo "3. Check the Actions tab to see the pipeline run"
echo ""
print_success "Setup complete! 🎉" 