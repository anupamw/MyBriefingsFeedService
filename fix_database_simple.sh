#!/bin/bash

# Simple database fix script
# Run this on your droplet

echo "🔧 Fixing database schema..."

# Connect to database and run the SQL fixes
psql "postgresql://fastapi:password@64.227.134.87:5432/briefings_feed" << 'EOF'

-- Add missing updated_at column to feed_items table
ALTER TABLE feed_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Add missing columns to user_categories table
ALTER TABLE user_categories ADD COLUMN IF NOT EXISTS keywords JSON;
ALTER TABLE user_categories ADD COLUMN IF NOT EXISTS sources JSON;
ALTER TABLE user_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Update existing records to have updated_at set to created_at
UPDATE feed_items SET updated_at = created_at WHERE updated_at IS NULL;

-- Show the updated table structure
\d feed_items;
\d user_categories;

EOF

echo "✅ Database schema fixed!"
echo ""
echo "🔄 Restarting ingestion service..."
kubectl rollout restart deployment/my-briefings-ingestion -n my-briefings

echo "⏳ Waiting for service to be ready..."
kubectl rollout status deployment/my-briefings-ingestion -n my-briefings

echo "📊 Checking pod status..."
kubectl get pods -n my-briefings

echo "🧪 Testing ingestion service..."
curl -s http://64.227.134.87:30101/ingestion/health | jq '.'

echo ""
echo "🎉 Database fix completed!" 