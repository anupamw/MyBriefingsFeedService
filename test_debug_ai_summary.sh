#!/bin/bash

# Test script for the debug AI summary endpoint (synchronous - no Celery yet)
# Make sure the feed ingestion service is running on port 8001

BASE_URL="http://localhost:8001"
USER_ID=1  # Adjust this to a valid user ID in your database

echo "🧪 Testing Debug AI Summary Endpoint (Synchronous)"
echo "=================================================="
echo "Base URL: $BASE_URL"
echo "User ID: $USER_ID"
echo "Note: Currently testing synchronous generation (Celery integration coming later)"
echo ""

# Test 1: Test with wait for completion (default)
echo "1. Testing with wait for completion (default)..."
echo "GET $BASE_URL/debug/ai-summary-test/$USER_ID"
echo "Response:"
curl -s "$BASE_URL/debug/ai-summary-test/$USER_ID" | jq '.' 2>/dev/null || curl -s "$BASE_URL/debug/ai-summary-test/$USER_ID"
echo ""
echo "---"
echo ""

# Test 2: Test without waiting for completion
echo "2. Testing without waiting for completion..."
echo "GET $BASE_URL/debug/ai-summary-test/$USER_ID?wait_for_completion=false"
echo "Response:"
curl -s "$BASE_URL/debug/ai-summary-test/$USER_ID?wait_for_completion=false" | jq '.' 2>/dev/null || curl -s "$BASE_URL/debug/ai-summary-test/$USER_ID?wait_for_completion=false"
echo ""
echo "---"
echo ""

# Test 3: Test with custom word limit
echo "3. Testing with custom word limit (500 words)..."
echo "GET $BASE_URL/debug/ai-summary-test/$USER_ID?max_words=500"
echo "Response:"
curl -s "$BASE_URL/debug/ai-summary-test/$USER_ID?max_words=500" | jq '.' 2>/dev/null || curl -s "$BASE_URL/debug/ai-summary-test/$USER_ID?max_words=500"
echo ""
echo "---"
echo ""

# Test 4: Test the regular AI summary endpoint
echo "4. Testing regular AI summary endpoint..."
echo "POST $BASE_URL/ai-summary/generate/$USER_ID?max_words=300"
echo "Response:"
curl -s -X POST "$BASE_URL/ai-summary/generate/$USER_ID?max_words=300" | jq '.' 2>/dev/null || curl -s -X POST "$BASE_URL/ai-summary/generate/$USER_ID?max_words=300"
echo ""
echo "---"
echo ""

# Test 5: Test the background endpoint (currently synchronous)
echo "5. Testing background endpoint (currently synchronous)..."
echo "POST $BASE_URL/ai-summary/generate-background/$USER_ID?max_words=300"
echo "Response:"
curl -s -X POST "$BASE_URL/ai-summary/generate-background/$USER_ID?max_words=300" | jq '.' 2>/dev/null || curl -s -X POST "$BASE_URL/ai-summary/generate-background/$USER_ID?max_words=300"
echo ""
echo "---"
echo ""

echo "=================================================="
echo "Debug tests completed!"
echo ""
echo "Note: If you want to test with a different user ID, modify the USER_ID variable in this script."
echo ""
echo "The debug endpoint will:"
echo "- Check if user has categories and feed items"
echo "- Generate AI summary synchronously (no Celery yet)"
echo "- Return detailed results including the generated summary"
echo ""
echo "Future: Celery integration will be added for background processing"
