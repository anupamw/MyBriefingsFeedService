#!/bin/bash

# Script to extract Perplexity API key from droplet and set up Kubernetes secrets
echo "🔧 Setting up Perplexity API Key in Kubernetes"
echo "=============================================="
echo ""

# Get the API key from the droplet
echo "📥 Extracting API key from droplet..."
PERPLEXITY_API_KEY=$(ssh root@64.227.134.87 "grep PERPLEXITY_API_KEY /root/.env | cut -d'=' -f2")

if [ -z "$PERPLEXITY_API_KEY" ]; then
    echo "❌ Error: Could not find PERPLEXITY_API_KEY in /root/.env on droplet"
    exit 1
fi

echo "✅ Found API key (length: ${#PERPLEXITY_API_KEY} characters)"

# Base64 encode the API key
ENCODED_KEY=$(echo -n "$PERPLEXITY_API_KEY" | base64)

echo ""
echo "🔧 Updating Kubernetes secrets..."

# Update the secrets file
cat > k8s/secrets/api-keys.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: api-keys
  namespace: my-briefings
type: Opaque
data:
  # Base64 encoded API keys
  perplexity-api-key: $ENCODED_KEY
  reddit-client-id: <base64-encoded-reddit-client-id>
  reddit-client-secret: <base64-encoded-reddit-client-secret>
EOF

echo "✅ Updated k8s/secrets/api-keys.yaml"
echo ""
echo "🔧 Applying secrets to Kubernetes..."

# Apply the secrets to the cluster
kubectl apply -f k8s/secrets/api-keys.yaml

echo ""
echo "✅ Kubernetes secrets updated successfully!"
echo "🔧 Restarting ingestion pods to pick up new secrets..."

# Restart the ingestion pods to pick up the new secrets
kubectl rollout restart deployment/my-briefings-ingestion -n my-briefings

echo ""
echo "🎉 Setup complete! The ingestion service should now be able to use the Perplexity API key."
echo "📝 You can test it by triggering an ingestion job:"
echo "   curl -X POST 'http://64.227.134.87:30101/ingest/perplexity?user_id=1'" 