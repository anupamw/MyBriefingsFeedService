#!/bin/bash

# Health check and restart script for local development
echo "🔍 Testing health checks for all services..."

# Test main app health
echo "Testing main app (port 8000)..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Main app: HEALTHY"
else
    echo "❌ Main app: UNHEALTHY"
fi

# Test feed-ingestion health
echo "Testing feed-ingestion (port 8001)..."
if curl -f http://localhost:8001/ingestion/health > /dev/null 2>&1; then
    echo "✅ Feed-ingestion: HEALTHY"
else
    echo "❌ Feed-ingestion: UNHEALTHY"
fi

# Test PostgreSQL health
echo "Testing PostgreSQL..."
if docker-compose -f docker-compose.local.yml exec postgres pg_isready -U fastapi -d briefings_feed > /dev/null 2>&1; then
    echo "✅ PostgreSQL: HEALTHY"
else
    echo "❌ PostgreSQL: UNHEALTHY"
fi

echo ""
echo "🔄 Restarting services with updated health checks..."
docker-compose -f docker-compose.local.yml restart

echo "⏳ Waiting for services to start..."
sleep 15

echo "📊 Checking service status..."
docker-compose -f docker-compose.local.yml ps

echo ""
echo "✅ Health check update complete!"
echo ""
echo "🌐 Services available at:"
echo "   Main App: http://localhost:8000"
echo "   Feed Ingestion: http://localhost:8001"
echo "   PostgreSQL: localhost:5432"

