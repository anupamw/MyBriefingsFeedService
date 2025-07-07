#!/usr/bin/env python3
"""
Local test script for the Feed Ingestion Service on droplet
Run this from your local machine to test the remote ingestion service
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration - Your droplet IP and NodePort
DROPLET_IP = "64.227.134.87"
NODE_PORT = "30101"
BASE_URL = f"http://{DROPLET_IP}:{NODE_PORT}"

def test_health_check():
    """Test the health check endpoint"""
    print("🔍 Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/ingestion/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health Check Passed: {data}")
            return True
        else:
            print(f"❌ Health Check Failed: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Cannot connect to ingestion service")
        print("   Make sure the service is running and NodePort is accessible")
        return False
    except Exception as e:
        print(f"❌ Health Check Error: {e}")
        return False

def test_basic_endpoints():
    """Test basic endpoints"""
    endpoints = [
        ("/data-sources", "Data Sources"),
        ("/ingestion-jobs", "Ingestion Jobs"),
        ("/feed-items?limit=3", "Feed Items"),
        ("/stats", "Stats")
    ]
    
    for endpoint, name in endpoints:
        print(f"\n🔍 Testing {name}...")
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    print(f"✅ {name}: Found {len(data)} items")
                else:
                    print(f"✅ {name}: {data}")
            else:
                print(f"❌ {name} failed: {response.text}")
        except Exception as e:
            print(f"❌ {name} error: {e}")

def test_ingestion_triggers():
    """Test ingestion trigger endpoints"""
    triggers = [
        {
            "endpoint": "/ingest/perplexity",
            "name": "Perplexity Ingestion",
            "payload": {"queries": ["AI news", "tech updates"]}
        },
        {
            "endpoint": "/ingest/reddit", 
            "name": "Reddit Ingestion",
            "payload": {"subreddits": ["programming"], "time_filter": "day"}
        },
        {
            "endpoint": "/ingest/social",
            "name": "Social Media Ingestion", 
            "payload": {"sources": ["twitter"]}
        }
    ]
    
    for trigger in triggers:
        print(f"\n🔍 Testing {trigger['name']}...")
        try:
            response = requests.post(
                f"{BASE_URL}{trigger['endpoint']}", 
                json=trigger['payload'],
                timeout=10
            )
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {trigger['name']} triggered: {data}")
            else:
                print(f"❌ {trigger['name']} failed: {response.text}")
        except Exception as e:
            print(f"❌ {trigger['name']} error: {e}")

def test_service_connectivity():
    """Test if we can reach the service"""
    print("🔍 Testing Service Connectivity...")
    print(f"Target URL: {BASE_URL}")
    
    try:
        # Try a simple GET request to see if service responds
        response = requests.get(f"{BASE_URL}/ingestion/health", timeout=5)
        print(f"✅ Service is reachable (Status: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to service")
        print("   Possible issues:")
        print("   1. Service not running on droplet")
        print("   2. NodePort not accessible")
        print("   3. Firewall blocking connection")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Feed Ingestion Service on Droplet")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    print("=" * 60)
    
    # First test connectivity
    if not test_service_connectivity():
        print("\n❌ Cannot reach the service. Please check:")
        print("   1. kubectl get pods -n my-briefings")
        print("   2. kubectl get svc -n my-briefings")
        print("   3. kubectl logs -n my-briefings my-briefings-ingestion-<pod-id>")
        return
    
    # Test health check
    if not test_health_check():
        print("\n❌ Health check failed. Service may not be ready.")
        return
    
    # Test basic endpoints
    test_basic_endpoints()
    
    # Test ingestion triggers
    test_ingestion_triggers()
    
    print("\n" + "=" * 60)
    print("✅ Feed Ingestion Service Tests Completed!")

if __name__ == "__main__":
    main() 