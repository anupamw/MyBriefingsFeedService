#!/bin/bash

# Test script for the AI Summary API endpoints
# Main service runs on NodePort 30100, Ingestion service on NodePort 30101

MAIN_SERVICE_URL="http://64.227.134.87:30100"
INGESTION_SERVICE_URL="http://64.227.134.87:30101"
JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbnVwYW13IiwiZXhwIjoxNzU1NDczOTAzfQ.T4rymU0aB5xKrm32G_fvpMsorRs140Hgu08VMs4bwVY"

echo "🧪 Testing AI Summary API Endpoints"
echo "=================================="
echo "Main Service URL: $MAIN_SERVICE_URL (NodePort 30100)"
echo "Ingestion Service URL: $INGESTION_SERVICE_URL (NodePort 30101)"
echo ""

echo "🔒 PROTECTED ENDPOINTS (Main Service - NodePort 30100)"
echo "======================================================"
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

echo "🔓 UNPROTECTED DEBUG ENDPOINT (Ingestion Service - NodePort 30101)"
echo "=================================================================="
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
echo "✅ Main Service (NodePort 30100): Protected endpoints with JWT authentication"
echo "✅ Ingestion Service (NodePort 30101): Debug endpoint for testing (no auth)"
echo ""
echo "🔐 To use protected endpoints:"
echo "curl -H 'Authorization: Bearer $JWT_TOKEN' '$MAIN_SERVICE_URL/ai-summary/generate?max_words=300'"
echo ""
echo "🧪 To test without auth:"
echo "curl '$INGESTION_SERVICE_URL/debug/ai-summary-test/1'"
echo ""
echo "🎯 Architecture:"
echo "- Production API: Main service (authenticated, NodePort 30100)"
echo "- Debug/Testing: Ingestion service (no auth required, NodePort 30101)"
echo ""
echo "📝 Port Mapping:"
echo "- Main Service: Internal port 8000 → NodePort 30100"
echo "- Ingestion Service: Internal port 8001 → NodePort 30101"
