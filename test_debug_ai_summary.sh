#!/bin/bash

# Test script for the AI Summary API endpoints
# Main service runs on port 8000, Ingestion service on port 30101

MAIN_SERVICE_URL="http://64.227.134.87:8000"
INGESTION_SERVICE_URL="http://64.227.134.87:30101"
JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbnVwYW13IiwiZXhwIjoxNzU1NDczOTAzfQ.T4rymU0aB5xKrm32G_fvpMsorRs140Hgu08VMs4bwVY"

echo "🧪 Testing AI Summary API Endpoints"
echo "=================================="
echo "Main Service URL: $MAIN_SERVICE_URL"
echo "Ingestion Service URL: $INGESTION_SERVICE_URL"
echo ""

echo "🔒 PROTECTED ENDPOINTS (Main Service - Port 8000)"
echo "================================================="
echo "These endpoints require a valid JWT token in the Authorization header"
echo ""

# Test 1: Protected status endpoint (should work with auth)
echo "1. Testing Protected Status endpoint with JWT token..."
echo "GET $MAIN_SERVICE_URL/ai-summary/status"
echo "Response:"
curl -s -H "Authorization: Bearer $JWT_TOKEN" "$MAIN_SERVICE_URL/ai-summary/status" | jq '.' 2>/dev/null || curl -s -H "Authorization: Bearer $JWT_TOKEN" "$MAIN_SERVICE_URL/ai-summary/status"
echo ""
echo "---"
echo ""

# Test 2: Protected generate endpoint (should work with auth)
echo "2. Testing Protected Generate endpoint with JWT token..."
echo "POST $MAIN_SERVICE_URL/ai-summary/generate?max_words=300"
echo "Response:"
curl -s -H "Authorization: Bearer $JWT_TOKEN" -X POST "$MAIN_SERVICE_URL/ai-summary/generate?max_words=300" | jq '.' 2>/dev/null || curl -s -H "Authorization: Bearer $JWT_TOKEN" -X POST "$MAIN_SERVICE_URL/ai-summary/generate?max_words=300"
echo ""
echo "---"
echo ""

# Test 3: Test without auth (should fail)
echo "3. Testing Protected endpoints WITHOUT auth (should fail)..."
echo "GET $MAIN_SERVICE_URL/ai-summary/status"
echo "Response (should be 401 Unauthorized):"
curl -s "$MAIN_SERVICE_URL/ai-summary/status" | jq '.' 2>/dev/null || curl -s "$MAIN_SERVICE_URL/ai-summary/status"
echo ""
echo "---"
echo ""

echo "🔓 UNPROTECTED DEBUG ENDPOINT (Ingestion Service - Port 30101)"
echo "=============================================================="
echo "This endpoint is for testing only and doesn't require authentication"
echo ""

# Test 4: Debug endpoint (no auth required)
echo "4. Testing Debug endpoint (no auth required)..."
echo "GET $INGESTION_SERVICE_URL/debug/ai-summary-test/1"
echo "Response:"
curl -s "$INGESTION_SERVICE_URL/debug/ai-summary-test/1" | jq '.' 2>/dev/null || curl -s "$INGESTION_SERVICE_URL/debug/ai-summary-test/1"
echo ""
echo "---"
echo ""

echo "📋 SUMMARY"
echo "=========="
echo "✅ Main Service (Port 8000): Protected endpoints with JWT authentication"
echo "✅ Ingestion Service (Port 30101): Debug endpoint for testing (no auth)"
echo ""
echo "🔐 To use protected endpoints:"
echo "curl -H 'Authorization: Bearer $JWT_TOKEN' '$MAIN_SERVICE_URL/ai-summary/generate?max_words=300'"
echo ""
echo "🧪 To test without auth:"
echo "curl '$INGESTION_SERVICE_URL/debug/ai-summary-test/1'"
echo ""
echo "🎯 Architecture:"
echo "- Production API: Main service (authenticated)"
echo "- Debug/Testing: Ingestion service (no auth required)"
