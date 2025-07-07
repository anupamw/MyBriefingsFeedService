#!/bin/bash

# Script to run database migration on the droplet
echo "🚀 Running database migration on droplet..."

# Copy migration script to droplet
echo "📤 Copying migration script to droplet..."
scp migrate_database.py fastapi@64.227.134.87:/home/fastapi/

# Run migration on droplet
echo "🔧 Running migration on droplet..."
ssh fastapi@64.227.134.87 << 'EOF'
cd /home/fastapi

# Set environment variables
export DATABASE_URL="postgresql://fastapi:password@64.227.134.87:5432/briefings_feed"

# Run the migration
python3 migrate_database.py

# Clean up
rm migrate_database.py
EOF

echo "✅ Migration completed!" 