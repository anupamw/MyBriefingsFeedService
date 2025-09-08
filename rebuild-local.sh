#!/bin/bash

# Rebuild and restart script for local development
# Usage: ./rebuild-local.sh [service-name]
# If service-name is provided, only that service will be rebuilt
# If no service-name is provided, all services will be rebuilt

SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "🔄 Stopping service: $SERVICE_NAME..."
    docker-compose -f docker-compose.local.yml stop "$SERVICE_NAME"
    
    echo "🔨 Rebuilding container: $SERVICE_NAME..."
    docker-compose -f docker-compose.local.yml build --no-cache "$SERVICE_NAME"
    
    echo "🚀 Starting service: $SERVICE_NAME..."
    docker-compose -f docker-compose.local.yml up -d "$SERVICE_NAME"
    
    echo "⏳ Waiting for service to start..."
    sleep 5
    
    echo "📊 Checking service status..."
    docker-compose -f docker-compose.local.yml ps "$SERVICE_NAME"
    
    echo "✅ Service $SERVICE_NAME rebuild complete!"
else
    echo "🔄 Stopping all services..."
    docker-compose -f docker-compose.local.yml down
    
    echo "🔨 Rebuilding all containers..."
    docker-compose -f docker-compose.local.yml build --no-cache
    
    echo "🚀 Starting all services..."
    docker-compose -f docker-compose.local.yml up -d
    
    echo "⏳ Waiting for services to start..."
    sleep 10
    
    echo "📊 Checking service status..."
    docker-compose -f docker-compose.local.yml ps
    
    echo "✅ Full rebuild complete!"
fi

echo ""
echo "🌐 Services available at:"
echo "   Main App: http://localhost:8000"
echo "   Feed Ingestion: http://localhost:8001"
echo "   PostgreSQL: localhost:5432"
echo ""
echo "📝 To view logs:"
if [ -n "$SERVICE_NAME" ]; then
    echo "   docker-compose -f docker-compose.local.yml logs -f $SERVICE_NAME"
else
    echo "   docker-compose -f docker-compose.local.yml logs -f"
fi
echo ""
echo "🛑 To stop services:"
echo "   docker-compose -f docker-compose.local.yml down"

