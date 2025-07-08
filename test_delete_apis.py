#!/usr/bin/env python3
"""
Test script for the new feed data deletion APIs
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"  # Main service
INGESTION_URL = "http://localhost:8001"  # Ingestion service

def test_delete_apis():
    """Test the new delete APIs"""
    print("🧪 Testing Feed Data Deletion APIs")
    print("=" * 50)
    
    # First, let's get a list of current feed items
    print("\n1. Getting current feed items...")
    try:
        response = requests.get(f"{BASE_URL}/feed?limit=5")
        if response.status_code == 200:
            items = response.json()
            print(f"✅ Found {len(items)} feed items")
            for item in items:
                print(f"  - ID: {item['id']}, Category: {item.get('category', 'N/A')}")
        else:
            print(f"❌ Failed to get feed items: {response.text}")
    except Exception as e:
        print(f"❌ Error getting feed items: {e}")
    
    # Test deleting feed data for a specific user (requires admin access)
    print("\n2. Testing delete feed data for user (requires admin login)...")
    print("   Note: This requires admin authentication (user ID 1)")
    
    # Test deleting feed data by category
    print("\n3. Testing delete feed data by category...")
    print("   Note: This requires admin authentication")
    
    # Test deleting all feed data
    print("\n4. Testing delete all feed data...")
    print("   ⚠️  WARNING: This will delete ALL feed data!")
    print("   Note: This requires admin authentication")
    
    print("\n" + "=" * 50)
    print("📋 API Endpoints Available:")
    print("=" * 50)
    
    print("\n🔐 Main Service (Port 8000):")
    print("DELETE /feed/delete/user/{user_id}?confirm=true")
    print("   - Delete all feed data for a specific user")
    print("   - Requires admin authentication (user ID 1)")
    print("   - Deletes feed items and user categories")
    
    print("\nDELETE /feed/delete/all?confirm=true")
    print("   - Delete ALL feed data for ALL users")
    print("   - Requires admin authentication")
    print("   - ⚠️  WARNING: This is destructive!")
    
    print("\nDELETE /feed/delete/category/{category_name}?confirm=true")
    print("   - Delete all feed data for a specific category")
    print("   - Requires admin authentication")
    print("   - Deletes feed items and user categories with that name")
    
    print("\n🔧 Ingestion Service (Port 8001):")
    print("DELETE /feed-items/delete/user/{user_id}?confirm=true")
    print("   - Delete all feed data for a specific user")
    print("   - No authentication required (for service-to-service calls)")
    
    print("\nDELETE /feed-items/delete/all?confirm=true")
    print("   - Delete ALL feed data")
    print("   - No authentication required")
    print("   - ⚠️  WARNING: This is destructive!")
    
    print("\nDELETE /feed-items/delete/category/{category_name}?confirm=true")
    print("   - Delete all feed data for a specific category")
    print("   - No authentication required")
    
    print("\n" + "=" * 50)
    print("💡 Usage Examples:")
    print("=" * 50)
    
    print("\n# Delete feed data for user ID 2 (requires admin login)")
    print("curl -X DELETE 'http://your-droplet:30100/feed/delete/user/2?confirm=true' \\")
    print("  -H 'Authorization: Bearer YOUR_ADMIN_TOKEN'")
    
    print("\n# Delete all feed data (requires admin login)")
    print("curl -X DELETE 'http://your-droplet:30100/feed/delete/all?confirm=true' \\")
    print("  -H 'Authorization: Bearer YOUR_ADMIN_TOKEN'")
    
    print("\n# Delete feed data for 'Technology' category (requires admin login)")
    print("curl -X DELETE 'http://your-droplet:30100/feed/delete/category/Technology?confirm=true' \\")
    print("  -H 'Authorization: Bearer YOUR_ADMIN_TOKEN'")
    
    print("\n# Using ingestion service (no auth required)")
    print("curl -X DELETE 'http://your-droplet:30101/feed-items/delete/user/2?confirm=true'")
    print("curl -X DELETE 'http://your-droplet:30101/feed-items/delete/all?confirm=true'")
    print("curl -X DELETE 'http://your-droplet:30101/feed-items/delete/category/Technology?confirm=true'")

if __name__ == "__main__":
    test_delete_apis() 