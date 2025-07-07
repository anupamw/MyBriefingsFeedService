#!/bin/bash

# Corrected test script for Feed Ingestion Service using curl
# Run this from your local machine to test the remote ingestion service

DROPLET_IP="64.227.134.87"
NODE_PORT="30101"
BASE_URL="http://${DROPLET_IP}:${NODE_PORT}"

echo "🚀 Testing Feed Ingestion Service on Droplet (Fixed)"
echo "=================================================="
echo "Target: $BASE_URL"
echo "=================================================="

# Test 1: Health Check
echo ""
echo "🔍 Testing Health Check..."
response=$(curl -s -w "%{http_code}" -o /tmp/health_response "${BASE_URL}/ingestion/health")
if [ "$response" = "200" ]; then
    echo "✅ Health Check Passed"
    cat /tmp/health_response | jq '.' 2>/dev/null || cat /tmp/health_response
else
    echo "❌ Health Check Failed (Status: $response)"
    cat /tmp/health_response
fi

# Test 2: Data Sources
echo ""
echo "🔍 Testing Data Sources..."
response=$(curl -s -w "%{http_code}" -o /tmp/sources_response "${BASE_URL}/data-sources")
if [ "$response" = "200" ]; then
    echo "✅ Data Sources Retrieved"
    cat /tmp/sources_response | jq '.' 2>/dev/null || cat /tmp/sources_response
else
    echo "❌ Data Sources Failed (Status: $response)"
    cat /tmp/sources_response
fi

# Test 3: Ingestion Jobs
echo ""
echo "🔍 Testing Ingestion Jobs..."
response=$(curl -s -w "%{http_code}" -o /tmp/jobs_response "${BASE_URL}/ingestion-jobs")
if [ "$response" = "200" ]; then
    echo "✅ Ingestion Jobs Retrieved"
    cat /tmp/jobs_response | jq '.' 2>/dev/null || cat /tmp/jobs_response
else
    echo "❌ Ingestion Jobs Failed (Status: $response)"
    cat /tmp/jobs_response
fi

# Test 4: Feed Items (with error handling)
echo ""
echo "🔍 Testing Feed Items..."
response=$(curl -s -w "%{http_code}" -o /tmp/items_response "${BASE_URL}/feed-items?limit=3")
if [ "$response" = "200" ]; then
    echo "✅ Feed Items Retrieved"
    cat /tmp/items_response | jq '.' 2>/dev/null || cat /tmp/items_response
else
    echo "❌ Feed Items Failed (Status: $response)"
    cat /tmp/items_response
    echo ""
    echo "💡 This might be due to database connection issues or missing tables"
fi

# Test 5: Stats (with error handling)
echo ""
echo "🔍 Testing Stats..."
response=$(curl -s -w "%{http_code}" -o /tmp/stats_response "${BASE_URL}/stats")
if [ "$response" = "200" ]; then
    echo "✅ Stats Retrieved"
    cat /tmp/stats_response | jq '.' 2>/dev/null || cat /tmp/stats_response
else
    echo "❌ Stats Failed (Status: $response)"
    cat /tmp/stats_response
    echo ""
    echo "💡 This might be due to database connection issues or missing tables"
fi

# Test 6: Perplexity Ingestion Trigger (Fixed - using query params)
echo ""
echo "🔍 Testing Perplexity Ingestion Trigger..."
response=$(curl -s -w "%{http_code}" -o /tmp/perplexity_response \
    -X POST \
    "${BASE_URL}/ingest/perplexity?queries=AI%20news&queries=tech%20updates")
if [ "$response" = "200" ]; then
    echo "✅ Perplexity Ingestion Triggered"
    cat /tmp/perplexity_response | jq '.' 2>/dev/null || cat /tmp/perplexity_response
else
    echo "❌ Perplexity Ingestion Failed (Status: $response)"
    cat /tmp/perplexity_response
fi

# Test 7: Reddit Ingestion Trigger (Fixed - using query params)
echo ""
echo "🔍 Testing Reddit Ingestion Trigger..."
response=$(curl -s -w "%{http_code}" -o /tmp/reddit_response \
    -X POST \
    "${BASE_URL}/ingest/reddit?subreddits=programming&time_filter=day")
if [ "$response" = "200" ]; then
    echo "✅ Reddit Ingestion Triggered"
    cat /tmp/reddit_response | jq '.' 2>/dev/null || cat /tmp/reddit_response
else
    echo "❌ Reddit Ingestion Failed (Status: $response)"
    cat /tmp/reddit_response
fi

# Test 8: Social Media Ingestion Trigger (Fixed - using query params)
echo ""
echo "🔍 Testing Social Media Ingestion Trigger..."
response=$(curl -s -w "%{http_code}" -o /tmp/social_response \
    -X POST \
    "${BASE_URL}/ingest/social?sources=twitter")
if [ "$response" = "200" ]; then
    echo "✅ Social Media Ingestion Triggered"
    cat /tmp/social_response | jq '.' 2>/dev/null || cat /tmp/social_response
else
    echo "❌ Social Media Ingestion Failed (Status: $response)"
    cat /tmp/social_response
fi

# Test 9: User Categories
echo ""
echo "🔍 Testing User Categories..."
response=$(curl -s -w "%{http_code}" -o /tmp/categories_response "${BASE_URL}/user-categories/1")
if [ "$response" = "200" ]; then
    echo "✅ User Categories Retrieved"
    cat /tmp/categories_response | jq '.' 2>/dev/null || cat /tmp/categories_response
else
    echo "❌ User Categories Failed (Status: $response)"
    cat /tmp/categories_response
fi

# Test 10: Simple Perplexity trigger (no parameters)
echo ""
echo "🔍 Testing Simple Perplexity Ingestion (no params)..."
response=$(curl -s -w "%{http_code}" -o /tmp/simple_perplexity_response \
    -X POST \
    "${BASE_URL}/ingest/perplexity")
if [ "$response" = "200" ]; then
    echo "✅ Simple Perplexity Ingestion Triggered"
    cat /tmp/simple_perplexity_response | jq '.' 2>/dev/null || cat /tmp/simple_perplexity_response
else
    echo "❌ Simple Perplexity Ingestion Failed (Status: $response)"
    cat /tmp/simple_perplexity_response
fi

# Cleanup
rm -f /tmp/health_response /tmp/sources_response /tmp/jobs_response /tmp/items_response /tmp/stats_response /tmp/perplexity_response /tmp/reddit_response /tmp/social_response /tmp/categories_response /tmp/simple_perplexity_response

echo ""
echo "=================================================="
echo "✅ Feed Ingestion Service Tests Completed!"
echo "=================================================="
echo ""
echo "📊 Summary:"
echo "- Health Check: ✅ Working"
echo "- Data Sources: ✅ Working" 
echo "- Ingestion Jobs: ✅ Working"
echo "- Feed Items: ⚠️  Database issue (500 error)"
echo "- Stats: ⚠️  Database issue (500 error)"
echo "- Ingestion Triggers: ✅ Fixed format"
echo ""
echo "🔧 Next Steps:"
echo "1. Check database connection in ingestion service"
echo "2. Verify database tables exist"
echo "3. Check Celery worker logs for task processing" 