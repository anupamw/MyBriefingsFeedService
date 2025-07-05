#!/bin/bash

# Script to set up .env file on the droplet
# Run this on the droplet to create the .env file with your API keys

echo "🔧 Setting up .env file on droplet..."

# Check if .env already exists
if [ -f ~/.env ]; then
    echo "⚠️  .env file already exists. Do you want to overwrite it? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "❌ Setup cancelled"
        exit 1
    fi
fi

echo "📝 Creating .env file..."
cat > ~/.env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://fastapi:password@64.227.134.87:5432/briefings_feed

# API Keys
PERPLEXITY_API_KEY=your_perplexity_api_key_here

# Application Settings
SECRET_KEY=your-super-secret-key-change-this-in-production
EOF

echo "✅ .env file created!"
echo ""
echo "🔑 Please edit the .env file and add your actual API keys:"
echo "   nano ~/.env"
echo ""
echo "📋 You need to replace:"
echo "   - your_perplexity_api_key_here with your actual Perplexity API key"
echo "   - your-super-secret-key-change-this-in-production with a secure secret key"
echo ""
echo "🚀 After editing, run the deployment again to pick up the new values." 