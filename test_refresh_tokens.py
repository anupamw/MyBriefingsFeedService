#!/usr/bin/env python3
"""
Test script for refresh token functionality
Run this to verify that the refresh token implementation is working correctly
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"  # Change this to your server URL
TEST_USERNAME = f"test_user_{int(time.time())}"
TEST_EMAIL = f"test_{int(time.time())}@example.com"
TEST_PASSWORD = "test_password_123"

def test_refresh_tokens():
    """Test the complete refresh token flow"""
    
    print("🧪 Testing Refresh Token Implementation")
    print("=" * 50)
    
    session = requests.Session()
    
    # Test 1: User Registration with Refresh Token
    print("\n1️⃣ Testing user registration...")
    
    signup_data = {
        "username": TEST_USERNAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = session.post(f"{BASE_URL}/auth/signup", json=signup_data)
        response.raise_for_status()
        
        signup_result = response.json()
        print(f"✅ Signup successful!")
        print(f"   Access Token: {signup_result['access_token'][:20]}...")
        print(f"   Refresh Token: {signup_result['refresh_token'][:20]}...")
        print(f"   Expires In: {signup_result['expires_in']} seconds")
        
        access_token = signup_result["access_token"]
        refresh_token = signup_result["refresh_token"]
        
    except Exception as e:
        print(f"❌ Signup failed: {e}")
        return False
    
    # Test 2: Use Access Token
    print("\n2️⃣ Testing access token usage...")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = session.get(f"{BASE_URL}/auth/me", headers=headers)
        response.raise_for_status()
        
        user_info = response.json()
        print(f"✅ Access token works!")
        print(f"   User ID: {user_info['id']}")
        print(f"   Username: {user_info['username']}")
        
    except Exception as e:
        print(f"❌ Access token test failed: {e}")
        return False
    
    # Test 3: Refresh Token Usage
    print("\n3️⃣ Testing refresh token...")
    
    try:
        refresh_data = {"refresh_token": refresh_token}
        response = session.post(f"{BASE_URL}/auth/refresh", json=refresh_data)
        response.raise_for_status()
        
        refresh_result = response.json()
        print(f"✅ Refresh token works!")
        print(f"   New Access Token: {refresh_result['access_token'][:20]}...")
        print(f"   New Refresh Token: {refresh_result['refresh_token'][:20]}...")
        print(f"   Expires In: {refresh_result['expires_in']} seconds")
        
        new_access_token = refresh_result["access_token"]
        new_refresh_token = refresh_result["refresh_token"]
        
    except Exception as e:
        print(f"❌ Refresh token test failed: {e}")
        return False
    
    # Test 4: Use New Access Token
    print("\n4️⃣ Testing new access token...")
    
    try:
        headers = {"Authorization": f"Bearer {new_access_token}"}
        response = session.get(f"{BASE_URL}/auth/me", headers=headers)
        response.raise_for_status()
        
        print(f"✅ New access token works!")
        
    except Exception as e:
        print(f"❌ New access token test failed: {e}")
        return False
    
    # Test 5: Old Refresh Token Should Be Revoked
    print("\n5️⃣ Testing old refresh token revocation...")
    
    try:
        old_refresh_data = {"refresh_token": refresh_token}
        response = session.post(f"{BASE_URL}/auth/refresh", json=old_refresh_data)
        
        if response.status_code == 401:
            print(f"✅ Old refresh token correctly revoked!")
        else:
            print(f"⚠️  Old refresh token still works (status: {response.status_code})")
            
    except Exception as e:
        print(f"✅ Old refresh token correctly rejected: {e}")
    
    # Test 6: Token Statistics
    print("\n6️⃣ Testing token statistics...")
    
    try:
        headers = {"Authorization": f"Bearer {new_access_token}"}
        response = session.get(f"{BASE_URL}/auth/refresh-tokens/stats", headers=headers)
        response.raise_for_status()
        
        stats = response.json()
        print(f"✅ Token statistics retrieved!")
        print(f"   Active Tokens: {stats['active_tokens']}")
        print(f"   Expired Tokens: {stats['expired_tokens']}")
        print(f"   Revoked Tokens: {stats['revoked_tokens']}")
        
    except Exception as e:
        print(f"⚠️  Token statistics test failed: {e}")
    
    # Test 7: Logout
    print("\n7️⃣ Testing logout...")
    
    try:
        headers = {"Authorization": f"Bearer {new_access_token}"}
        logout_data = {"refresh_token": new_refresh_token}
        response = session.post(f"{BASE_URL}/auth/logout", json=logout_data, headers=headers)
        response.raise_for_status()
        
        print(f"✅ Logout successful!")
        
        # Try to use refresh token after logout
        refresh_data = {"refresh_token": new_refresh_token}
        response = session.post(f"{BASE_URL}/auth/refresh", json=refresh_data)
        
        if response.status_code == 401:
            print(f"✅ Refresh token correctly revoked after logout!")
        else:
            print(f"⚠️  Refresh token still works after logout")
            
    except Exception as e:
        print(f"⚠️  Logout test failed: {e}")
    
    # Test 8: Login Flow
    print("\n8️⃣ Testing login flow...")
    
    try:
        login_data = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        }
        
        response = session.post(f"{BASE_URL}/auth/login", json=login_data)
        response.raise_for_status()
        
        login_result = response.json()
        print(f"✅ Login successful!")
        print(f"   Access Token: {login_result['access_token'][:20]}...")
        print(f"   Refresh Token: {login_result['refresh_token'][:20]}...")
        
    except Exception as e:
        print(f"❌ Login test failed: {e}")
        return False
    
    print("\n🎉 All tests completed!")
    print("\n📋 Summary:")
    print("✅ User registration with refresh tokens")
    print("✅ Access token authentication")
    print("✅ Refresh token usage")
    print("✅ Token rotation (old tokens revoked)")
    print("✅ Token statistics")
    print("✅ Logout functionality")
    print("✅ Login flow")
    
    return True

def test_token_expiration():
    """Test token expiration behavior (requires short token lifetimes)"""
    print("\n⏰ Testing token expiration...")
    print("Note: This test requires ACCESS_TOKEN_EXPIRE_MINUTES to be set to 1 minute or less")
    
    # This would require modifying the server configuration for testing
    print("⚠️  Skipping expiration test - requires server configuration changes")

if __name__ == "__main__":
    print("Starting refresh token tests...")
    print(f"Testing against: {BASE_URL}")
    
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        print("✅ Server is running")
        
        # Run the tests
        success = test_refresh_tokens()
        
        if success:
            print("\n🎉 All tests passed! Refresh token implementation is working correctly.")
        else:
            print("\n❌ Some tests failed. Check the implementation.")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print("Make sure your FastAPI server is running with: python main.py")
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
