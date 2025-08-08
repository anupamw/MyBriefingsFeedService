import json
import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add debugging for import paths
print(f"[DEBUG] feed_filter.py: Current working directory: {os.getcwd()}")
print(f"[DEBUG] feed_filter.py: __file__: {__file__}")
print(f"[DEBUG] feed_filter.py: Current sys.path: {sys.path}")

# Add the current directory's parent to Python path for relative imports
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
print(f"[DEBUG] feed_filter.py: current_dir: {current_dir}")
print(f"[DEBUG] feed_filter.py: parent_dir: {parent_dir}")

sys.path.insert(0, parent_dir)
print(f"[DEBUG] feed_filter.py: Updated sys.path: {sys.path}")

class FeedItemFilter:
    """Filter feed items for relevance using Perplexity AI"""
    
    def __init__(self):
        self.perplexity_client = None
        self._init_perplexity_client()
    
    def _init_perplexity_client(self):
        """Initialize Perplexity client"""
        print(f"[DEBUG] feed_filter.py: Starting _init_perplexity_client")
        try:
            # Use relative import from the parent directory
            print(f"[DEBUG] feed_filter.py: Attempting to import PerplexityRunner")
            from runners.perplexity_runner import PerplexityRunner
            print(f"[DEBUG] feed_filter.py: Successfully imported PerplexityRunner")
            self.perplexity_client = PerplexityRunner()
            print(f"[DEBUG] feed_filter.py: Successfully created PerplexityRunner instance")
        except ImportError as e:
            print(f"[ERROR] feed_filter.py: ImportError: {e}")
            print(f"[DEBUG] feed_filter.py: sys.path at error: {sys.path}")
            self.perplexity_client = None
        except Exception as e:
            print(f"[ERROR] feed_filter.py: Failed to initialize Perplexity client: {e}")
            print(f"[DEBUG] feed_filter.py: Exception type: {type(e)}")
            self.perplexity_client = None
    
    def create_filtering_prompt(self, category_name: str, short_summary: str, feed_items: List[Dict]) -> str:
        """Create a prompt for Perplexity to filter feed items"""
        
        # Format feed items for the prompt
        items_text = []
        for i, item in enumerate(feed_items, 1):
            title = item.get('title', '')
            summary = item.get('summary', '')
            content = item.get('content', '')
            source = item.get('source', '')
            
            # Truncate content if too long
            if len(content) > 500:
                content = content[:500] + "..."
            
            items_text.append(f"""
Item {i}:
- Title: {title}
- Summary: {summary}
- Content: {content}
- Source: {source}
""")
        
        items_block = "\n".join(items_text)
        
        prompt = f"""
You are a content filtering expert. Your task is to determine which feed items are relevant to a specific category.

CATEGORY INFORMATION:
- Category Name: "{category_name}"
- Category Summary: "{short_summary}"

FEED ITEMS TO EVALUATE:
{items_block}

INSTRUCTIONS:
1. Analyze each feed item carefully
2. Determine if the item is relevant to the category based on:
   - Topic alignment with the category
   - Content relevance to the category summary
   - Whether the item would be valuable for someone interested in this category

3. Return a JSON response with the following format:
{{
    "evaluations": [
        {{
            "item_number": 1,
            "is_relevant": true/false,
            "reason": "Brief explanation of why this item is relevant or not"
        }},
        {{
            "item_number": 2,
            "is_relevant": true/false,
            "reason": "Brief explanation of why this item is relevant or not"
        }}
        // ... continue for all items
    ],
    "summary": {{
        "total_items": <number>,
        "relevant_items": <number>,
        "irrelevant_items": <number>
    }}
}}

IMPORTANT:
- Be strict but fair in your evaluation
- Consider the category context and user intent
- If in doubt, err on the side of relevance
- Provide clear, concise reasoning for each decision
- Ensure the JSON is properly formatted and valid
"""
        
        return prompt
    
    def filter_feed_items(self, category_name: str, short_summary: str, feed_items: List[Dict]) -> Dict[str, Any]:
        """Filter feed items using Perplexity AI"""
        
        if not self.perplexity_client:
            print("[ERROR] Perplexity client not available")
            return {
                "success": False,
                "error": "Perplexity client not available",
                "filtered_items": feed_items,
                "evaluations": []
            }
        
        if not feed_items:
            return {
                "success": True,
                "filtered_items": [],
                "evaluations": [],
                "original_count": 0,
                "filtered_count": 0
            }
        
        try:
            # Create the filtering prompt
            prompt = self.create_filtering_prompt(category_name, short_summary, feed_items)
            
            # Call Perplexity API
            response = self.perplexity_client.query_perplexity(prompt)
            
            if not response or not response.get('choices'):
                print("[ERROR] No response from Perplexity")
                return {
                    "success": False,
                    "error": "No response from Perplexity",
                    "filtered_items": feed_items,
                    "evaluations": []
                }
            
            # Extract the content from the response
            content = ""
            if response.get('choices') and len(response['choices']) > 0:
                content = response['choices'][0]['message']['content']
            
            if not content:
                print("[ERROR] No content in Perplexity response")
                return {
                    "success": False,
                    "error": "No content in Perplexity response",
                    "filtered_items": feed_items,
                    "evaluations": []
                }
            
            # Parse the JSON response
            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse Perplexity response as JSON: {e}")
                print(f"[ERROR] Response: {content}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {e}",
                    "filtered_items": feed_items,
                    "evaluations": []
                }
            
            # Extract relevant items
            evaluations = result.get('evaluations', [])
            relevant_items = []
            
            for eval_item in evaluations:
                item_number = eval_item.get('item_number', 0)
                is_relevant = eval_item.get('is_relevant', False)
                
                if is_relevant and 1 <= item_number <= len(feed_items):
                    relevant_items.append(feed_items[item_number - 1])
            
            return {
                "success": True,
                "filtered_items": relevant_items,
                "evaluations": evaluations,
                "summary": result.get('summary', {}),
                "original_count": len(feed_items),
                "filtered_count": len(relevant_items)
            }
            
        except Exception as e:
            print(f"[ERROR] Error filtering feed items: {e}")
            return {
                "success": False,
                "error": str(e),
                "filtered_items": feed_items,
                "evaluations": []
            }

# Global instance
feed_filter = FeedItemFilter() 