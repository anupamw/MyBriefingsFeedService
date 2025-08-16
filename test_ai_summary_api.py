#!/usr/bin/env python3
"""
Test script for AI Summary API endpoints
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8001"  # Adjust if your service runs on a different port
TEST_USER_ID = 1  # Adjust to a valid user ID in your database

def test_ai_summary_status():
    """Test the AI summary status endpoint"""
    print("Testing AI Summary Status endpoint...")
    
    url = f"{BASE_URL}/ai-summary/status/{TEST_USER_ID}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response:")
            print(json.dumps(data, indent=2))
            
            if data.get("can_generate_summary"):
                print("✅ User can generate summary")
            else:
                print("❌ User cannot generate summary")
                print(f"Reason: {data.get('message', 'Unknown')}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

def test_ai_summary_generation():
    """Test the AI summary generation endpoint"""
    print("\nTesting AI Summary Generation endpoint...")
    
    url = f"{BASE_URL}/ai-summary/generate/{TEST_USER_ID}"
    params = {"max_words": 300}
    
    try:
        print("Generating summary (this may take a while)...")
        response = requests.post(url, params=params)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response:")
            print(json.dumps(data, indent=2))
            
            print(f"\nSummary ({data.get('word_count', 0)} words):")
            print("-" * 50)
            print(data.get('summary', 'No summary generated'))
            print("-" * 50)
            
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

def test_background_summary_generation():
    """Test the background AI summary generation endpoint"""
    print("\nTesting Background AI Summary Generation endpoint...")
    
    url = f"{BASE_URL}/ai-summary/generate-background/{TEST_USER_ID}"
    params = {"max_words": 300}
    
    try:
        response = requests.post(url, params=params)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response:")
            print(json.dumps(data, indent=2))
            
            task_id = data.get("task_id")
            if task_id:
                print(f"\nTask ID: {task_id}")
                print("You can check task status using the /task/{task_id} endpoint")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

def test_task_status(task_id):
    """Test the task status endpoint"""
    print(f"\nTesting Task Status endpoint for task {task_id}...")
    
    url = f"{BASE_URL}/task/{task_id}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response:")
            print(json.dumps(data, indent=2))
            
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

def main():
    """Main test function"""
    print("🧪 AI Summary API Test Suite")
    print("=" * 50)
    
    # Test 1: Check if user can generate summary
    test_ai_summary_status()
    
    # Test 2: Generate summary synchronously
    test_ai_summary_generation()
    
    # Test 3: Generate summary in background
    test_background_summary_generation()
    
    # Test 4: Check task status (if background task was created)
    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nTo check task status, use the task ID from the background generation response.")

if __name__ == "__main__":
    main()
