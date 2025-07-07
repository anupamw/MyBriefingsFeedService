#!/bin/bash

# Script to update .env file on droplet with Perplexity API key
echo "🔧 Perplexity API Key Setup"
echo "=========================="
echo ""
echo "Please enter your Perplexity API key:"
read -s PERPLEXITY_API_KEY

if [ -z "$PERPLEXITY_API_KEY" ]; then
    echo "❌ Error: No API key provided"
    exit 1
fi

echo ""
echo "🔧 Updating .env file on droplet..."

# Update the .env file on the droplet
ssh root@64.227.134.87 << EOF
    # Backup current .env
    cp /root/.env /root/.env.backup
    
    # Update PERPLEXITY_API_KEY in .env
    sed -i "s/PERPLEXITY_API_KEY=/PERPLEXITY_API_KEY=$PERPLEXITY_API_KEY/" /root/.env
    
    # Verify the update
    echo "✅ Updated .env file:"
    grep PERPLEXITY_API_KEY /root/.env
EOF

echo ""
echo "✅ .env file updated successfully!"
echo "🔧 Next step: Update Kubernetes secrets with the API key"
echo ""
echo "To get the base64 encoded value for Kubernetes:"
echo "echo -n '$PERPLEXITY_API_KEY' | base64" 