#!/bin/bash

# Script to update Kubernetes secrets with Perplexity API key
echo "🔧 Kubernetes Secrets Update"
echo "==========================="
echo ""
echo "Please enter your Perplexity API key:"
read -s PERPLEXITY_API_KEY

if [ -z "$PERPLEXITY_API_KEY" ]; then
    echo "❌ Error: No API key provided"
    exit 1
fi

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
echo "🔧 You may need to restart the ingestion pods to pick up the new secrets"
echo ""
echo "To restart the ingestion pods:"
echo "kubectl rollout restart deployment/my-briefings-ingestion -n my-briefings" 