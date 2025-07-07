#!/usr/bin/env python3
"""
Test script for the Feed Ingestion Service
Tests all endpoints and functionality
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://64.227.134.87:30101"  # NodePort for ingestion service
HEALTH_ENDPOINT = "/ingestion/health"
DATA_SOURCES_ENDPOINT = "/data-sources"
INGESTION_JOBS_ENDPOINT = "/ingestion-jobs"
FEED_ITEMS_ENDPOINT = "/feed-items"
STATS_ENDPOINT = "/stats"

def test_health_check():
    """Test the health check endpoint"""
    print("🔍 Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}{HEALTH_ENDPOINT}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health Check Passed: {data}")
            return True
        else:
            print(f"❌ Health Check Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health Check Error: {e}")
        return False

def test_data_sources():
    """Test data sources endpoints"""
    print("\n🔍 Testing Data Sources...")
    
    # Get all data sources
    try:
        response = requests.get(f"{BASE_URL}{DATA_SOURCES_ENDPOINT}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            sources = response.json()
            print(f"✅ Found {len(sources)} data sources")
            for source in sources:
                print(f"  - {source['display_name']} ({source['name']}) - Active: {source['is_active']}")
        else:
            print(f"❌ Failed to get data sources: {response.text}")
    except Exception as e:
        print(f"❌ Data Sources Error: {e}")

def test_ingestion_jobs():
    """Test ingestion jobs endpoint"""
    print("\n🔍 Testing Ingestion Jobs...")
    
    try:
        response = requests.get(f"{BASE_URL}{INGESTION_JOBS_ENDPOINT}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            jobs = response.json()
            print(f"✅ Found {len(jobs)} ingestion jobs")
            for job in jobs[:5]:  # Show first 5 jobs
                print(f"  - {job['job_type']} ({job['status']}) - Created: {job['created_at']}")
        else:
            print(f"❌ Failed to get ingestion jobs: {response.text}")
    except Exception as e:
        print(f"❌ Ingestion Jobs Error: {e}")

def test_feed_items():
    """Test feed items endpoint"""
    print("\n🔍 Testing Feed Items...")
    
    try:
        response = requests.get(f"{BASE_URL}{FEED_ITEMS_ENDPOINT}?limit=5")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            items = response.json()
            print(f"✅ Found {len(items)} feed items")
            for item in items:
                print(f"  - {item['title'][:50]}... ({item['source']})")
        else:
            print(f"❌ Failed to get feed items: {response.text}")
    except Exception as e:
        print(f"❌ Feed Items Error: {e}")

def test_stats():
    """Test stats endpoint"""
    print("\n🔍 Testing Stats...")
    
    try:
        response = requests.get(f"{BASE_URL}{STATS_ENDPOINT}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Stats retrieved: {stats}")
        else:
            print(f"❌ Failed to get stats: {response.text}")
    except Exception as e:
        print(f"❌ Stats Error: {e}")

def test_perplexity_ingestion():
    """Test Perplexity ingestion trigger"""
    print("\n🔍 Testing Perplexity Ingestion...")
    
    try:
        # Test with sample queries
        payload = {
            "queries": ["AI news", "tech updates"]
        }
        response = requests.post(f"{BASE_URL}/ingest/perplexity", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Perplexity ingestion triggered: {data}")
            return data.get('task_id')
        else:
            print(f"❌ Failed to trigger Perplexity ingestion: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Perplexity Ingestion Error: {e}")
        return None

def test_reddit_ingestion():
    """Test Reddit ingestion trigger"""
    print("\n🔍 Testing Reddit Ingestion...")
    
    try:
        payload = {
            "subreddits": ["programming", "technology"],
            "time_filter": "day"
        }
        response = requests.post(f"{BASE_URL}/ingest/reddit", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Reddit ingestion triggered: {data}")
            return data.get('task_id')
        else:
            print(f"❌ Failed to trigger Reddit ingestion: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Reddit Ingestion Error: {e}")
        return None

def test_social_ingestion():
    """Test Social media ingestion trigger"""
    print("\n🔍 Testing Social Media Ingestion...")
    
    try:
        payload = {
            "sources": ["twitter", "linkedin"]
        }
        response = requests.post(f"{BASE_URL}/ingest/social", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Social media ingestion triggered: {data}")
            return data.get('task_id')
        else:
            print(f"❌ Failed to trigger social media ingestion: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Social Media Ingestion Error: {e}")
        return None

def test_task_status(task_id: str):
    """Test task status endpoint"""
    if not task_id:
        return
    
    print(f"\n🔍 Testing Task Status for {task_id}...")
    
    try:
        response = requests.get(f"{BASE_URL}/task/{task_id}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Task status: {data}")
        else:
            print(f"❌ Failed to get task status: {response.text}")
    except Exception as e:
        print(f"❌ Task Status Error: {e}")

def test_user_categories():
    """Test user categories endpoint"""
    print("\n🔍 Testing User Categories...")
    
    try:
        # Test with user ID 1
        response = requests.get(f"{BASE_URL}/user-categories/1")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            categories = response.json()
            print(f"✅ User categories: {categories}")
        else:
            print(f"❌ Failed to get user categories: {response.text}")
    except Exception as e:
        print(f"❌ User Categories Error: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting Feed Ingestion Service Tests")
    print("=" * 50)
    
    # Test basic endpoints
    health_ok = test_health_check()
    if not health_ok:
        print("❌ Health check failed. Stopping tests.")
        return
    
    test_data_sources()
    test_ingestion_jobs()
    test_feed_items()
    test_stats()
    test_user_categories()
    
    # Test ingestion triggers
    perplexity_task = test_perplexity_ingestion()
    reddit_task = test_reddit_ingestion()
    social_task = test_social_ingestion()
    
    # Test task status if tasks were created
    if perplexity_task:
        test_task_status(perplexity_task)
    if reddit_task:
        test_task_status(reddit_task)
    if social_task:
        test_task_status(social_task)
    
    print("\n" + "=" * 50)
    print("✅ Feed Ingestion Service Tests Completed!")

if __name__ == "__main__":
    main() 