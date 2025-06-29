#!/usr/bin/env python3
"""
Simple test script for the Football Transfers API
This can be used in CI/CD pipelines to verify the app works correctly
"""

import requests
import sys
import time

def test_health_endpoint(base_url):
    """Test the health endpoint"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health endpoint test passed")
            return True
        else:
            print(f"❌ Health endpoint test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False

def test_root_endpoint(base_url):
    """Test the root endpoint"""
    try:
        response = requests.get(base_url, timeout=10)
        if response.status_code == 200:
            print("✅ Root endpoint test passed")
            return True
        else:
            print(f"❌ Root endpoint test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Root endpoint test failed: {e}")
        return False

def test_docs_endpoint(base_url):
    """Test the docs endpoint"""
    try:
        response = requests.get(f"{base_url}/docs", timeout=10)
        if response.status_code == 200:
            print("✅ Docs endpoint test passed")
            return True
        else:
            print(f"❌ Docs endpoint test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Docs endpoint test failed: {e}")
        return False

def main():
    """Run all tests"""
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    print(f"🧪 Testing application at: {base_url}")
    
    tests = [
        test_health_endpoint,
        test_root_endpoint,
        test_docs_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test(base_url):
            passed += 1
        time.sleep(1)  # Small delay between tests
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 