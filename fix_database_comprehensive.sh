#!/bin/bash

# Comprehensive database schema fix script
# This script adds all missing columns that the ingestion service expects

set -e

echo "🔧 Starting comprehensive database schema fix..."

# Database connection details
DB_HOST="64.227.134.87"
DB_PORT="5432"
DB_NAME="briefings_feed"
DB_USER="fastapi"
DB_PASSWORD="password"

# Connection string
DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo "📊 Database: ${DB_NAME}"
echo "🔗 Host: ${DB_HOST}:${DB_PORT}"
echo "👤 User: ${DB_USER}"

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "❌ Error: psql is not installed. Please install PostgreSQL client."
    exit 1
fi

# Test database connection
echo "🔍 Testing database connection..."
if ! psql "$DB_URL" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to database. Please check your connection details."
    exit 1
fi
echo "✅ Database connection successful"

# Run the comprehensive fix
echo "🔧 Applying comprehensive database schema fix..."
psql "$DB_URL" -f fix_database_comprehensive.sql

echo "✅ Comprehensive database schema fix completed!"

# Verify the fix by testing the problematic queries
echo "🔍 Verifying the fix..."

echo "📊 Testing feed_items table structure..."
psql "$DB_URL" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'feed_items' ORDER BY ordinal_position;"

echo ""
echo "📊 Testing user_categories table structure..."
psql "$DB_URL" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'user_categories' ORDER BY ordinal_position;"

echo ""
echo "📊 Testing a sample query that was failing..."
psql "$DB_URL" -c "SELECT COUNT(*) FROM feed_items;"

echo ""
echo "🎉 Database schema fix verification completed!"
echo "📝 The ingestion service should now work properly." 