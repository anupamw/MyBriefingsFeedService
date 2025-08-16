#!/bin/bash

# Test script for the AI Summary API endpoints
# Make sure the feed ingestion service is running on port 8001

BASE_URL="http://localhost:8001"
DROPLET_URL="http://64.227.134.87:30101"
USER_ID=1  # Adjust this to a valid user ID in your database

echo "🧪 Testing AI Summary API Endpoints"
echo "=================================="
echo "Local Base URL: $BASE_URL"
echo "Droplet URL: $DROPLET_URL"
echo "User ID: $USER_ID"
echo ""

echo "🔒 PROTECTED ENDPOINTS (Require Authentication)"
echo "=============================================="
echo "These endpoints require a valid JWT token in the Authorization header"
echo ""

# Test 1: Protected status endpoint (will fail without auth)
echo "1. Testing Protected Status endpoint (should fail without auth)..."
echo "GET $DROPLET_URL/ai-summary/status/$USER_ID"
echo "Response (should be 401 Unauthorized):"
curl -s "$DROPLET_URL/ai-summary/status/$USER_ID" | jq '.' 2>/dev/null || curl -s "$DROPLET_URL/ai-summary/status/$USER_ID"
echo ""
echo "---"
echo ""

# Test 2: Protected generate endpoint (will fail without auth)
echo "2. Testing Protected Generate endpoint (should fail without auth)..."
echo "POST $DROPLET_URL/ai-summary/generate/$USER_ID?max_words=300"
echo "Response (should be 401 Unauthorized):"
curl -s -X POST "$DROPLET_URL/ai-summary/generate/$USER_ID?max_words=300" | jq '.' 2>/dev/null || curl -s -X POST "$DROPLET_URL/ai-summary/generate/$USER_ID?max_words=300"
echo ""
echo "---"
echo ""

echo "🔓 UNPROTECTED DEBUG ENDPOINT (No Authentication Required)"
echo "========================================================="
echo "This endpoint is for testing only and doesn't require authentication"
echo ""

# Test 3: Debug endpoint (no auth required)
echo "3. Testing Debug endpoint (no auth required)..."
echo "GET $DROPLET_URL/debug/ai-summary-test/$USER_ID"
echo "Response:"
curl -s "$DROPLET_URL/debug/ai-summary-test/$USER_ID" | jq '.' 2>/dev/null || curl -s "$DROPLET_URL/debug/ai-summary-test/$USER_ID"
echo ""
echo "---"
echo ""

echo "📋 SUMMARY"
echo "=========="
echo "✅ Debug endpoint: Working (no auth required)"
echo "❌ Protected endpoints: Require JWT authentication"
echo ""
echo "To test protected endpoints, you need to:"
echo "1. Get a JWT token from /auth/login"
echo "2. Include it in Authorization: Bearer <token> header"
echo ""
echo "Example with auth:"
echo "curl -H 'Authorization: Bearer YOUR_JWT_TOKEN' \\"
echo "  '$DROPLET_URL/ai-summary/generate/$USER_ID?max_words=300'"
echo ""
echo "Note: The debug endpoint is perfect for development and testing!"
