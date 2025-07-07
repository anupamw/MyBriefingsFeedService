#!/usr/bin/env python3
"""
Script to test Perplexity API with correct model name
"""

import os
import requests
import json
from dotenv import load_dotenv

def test_perplexity_api():
    """Test Perplexity API with correct model name"""
    load_dotenv()
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not found in environment")
        return
    
    print(f"✅ Found API key (length: {len(api_key)})")
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that provides concise, informative summaries of current events and trending topics."
            },
            {
                "role": "user",
                "content": "What is the latest Manchester United transfer news from the last 24 hours?"
            }
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    print("🔍 Testing Perplexity API with model: sonar")
    print(f"📡 URL: {url}")
    print(f"📝 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"📊 Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API call successful!")
            print(f"📄 Response: {json.dumps(result, indent=2)}")
            
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                print(f"📝 Content: {content}")
            else:
                print("⚠️  No content in response")
        else:
            print(f"❌ API call failed with status {response.status_code}")
            print(f"📄 Error response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_perplexity_api() 