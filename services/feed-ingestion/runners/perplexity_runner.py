import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from dotenv import load_dotenv

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from shared.database.connection import SessionLocal
from shared.models.database_models import DataSource, FeedItem, IngestionJob, ContentCache
from services.feed_ingestion.celery_app import celery_app

load_dotenv()

class PerplexityRunner:
    """Runner for Perplexity API integration"""
    
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.db = SessionLocal()
        
    def get_data_source(self) -> Optional[DataSource]:
        """Get Perplexity data source configuration"""
        return self.db.query(DataSource).filter(
            DataSource.name == "perplexity",
            DataSource.is_active == True
        ).first()
    
    def create_cache_key(self, query: str, model: str) -> str:
        """Create cache key for query"""
        import hashlib
        cache_data = f"{query}:{model}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    def get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Get cached response if available and not expired"""
        cache_entry = self.db.query(ContentCache).filter(
            ContentCache.cache_key == cache_key,
            ContentCache.data_source == "perplexity",
            ContentCache.expires_at > datetime.utcnow()
        ).first()
        
        return cache_entry.response_data if cache_entry else None
    
    def cache_response(self, cache_key: str, response_data: Dict, expire_hours: int = 24):
        """Cache API response"""
        expires_at = datetime.utcnow() + timedelta(hours=expire_hours)
        
        cache_entry = ContentCache(
            cache_key=cache_key,
            data_source="perplexity",
            response_data=response_data,
            expires_at=expires_at
        )
        
        self.db.add(cache_entry)
        self.db.commit()
    
    def query_perplexity(self, query: str, model: str = "llama-3.1-sonar-small-128k-online") -> Optional[Dict]:
        """Query Perplexity API"""
        if not self.api_key:
            print("PERPLEXITY_API_KEY not found in environment")
            return None
        
        # Check cache first
        cache_key = self.create_cache_key(query, model)
        cached_response = self.get_cached_response(cache_key)
        if cached_response:
            return cached_response
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides concise, informative summaries of current events and trending topics. Focus on factual information and provide relevant context."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            # Cache the response
            self.cache_response(cache_key, result)
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Error querying Perplexity API: {e}")
            return None
    
    def extract_content_from_response(self, response: Dict) -> List[Dict[str, Any]]:
        """Extract structured content from Perplexity response"""
        content_items = []
        
        try:
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]
                
                # Parse the content and extract structured information
                # This is a simplified parser - you might want to make it more sophisticated
                lines = content.split('\n')
                current_item = {}
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        if current_item:
                            content_items.append(current_item)
                            current_item = {}
                        continue
                    
                    # Simple parsing logic - adjust based on actual response format
                    if line.startswith('**') and line.endswith('**'):
                        if current_item:
                            content_items.append(current_item)
                        current_item = {"title": line.strip('*')}
                    elif line.startswith('http'):
                        current_item["url"] = line
                    elif len(line) > 50:  # Likely content
                        current_item["summary"] = line
                
                if current_item:
                    content_items.append(current_item)
            
        except Exception as e:
            print(f"Error extracting content from response: {e}")
        
        return content_items
    
    def save_feed_items(self, content_items: List[Dict], data_source: DataSource) -> Dict[str, int]:
        """Save extracted content as feed items"""
        created = 0
        updated = 0
        
        for item in content_items:
            try:
                # Check if item already exists (by title and source)
                existing_item = self.db.query(FeedItem).filter(
                    FeedItem.title == item.get("title"),
                    FeedItem.data_source_id == data_source.id
                ).first()
                
                if existing_item:
                    # Update existing item
                    existing_item.summary = item.get("summary", existing_item.summary)
                    existing_item.url = item.get("url", existing_item.url)
                    existing_item.updated_at = datetime.utcnow()
                    updated += 1
                else:
                    # Create new item
                    feed_item = FeedItem(
                        title=item.get("title", "Untitled"),
                        summary=item.get("summary", ""),
                        url=item.get("url", ""),
                        source="Perplexity AI",
                        data_source_id=data_source.id,
                        published_at=datetime.utcnow(),
                        raw_data=item,
                        category="AI Generated",
                        tags=["ai", "perplexity"]
                    )
                    self.db.add(feed_item)
                    created += 1
                
            except Exception as e:
                print(f"Error saving feed item: {e}")
                continue
        
        self.db.commit()
        return {"created": created, "updated": updated}

@celery_app.task(bind=True)
def ingest_perplexity(self, queries: List[str] = None):
    """Celery task for Perplexity ingestion"""
    if queries is None:
        queries = [
            "What are the top technology news stories today?",
            "What are the major world events happening right now?",
            "What are the latest developments in AI and machine learning?",
            "What are the trending topics in science and research?",
            "What are the key business and finance news today?"
        ]
    
    runner = PerplexityRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("Perplexity data source not found or inactive")
        return {"error": "Data source not found"}
    
    # Create ingestion job record
    job = IngestionJob(
        job_type="perplexity",
        status="running",
        started_at=datetime.utcnow(),
        parameters={"queries": queries},
        data_source_id=data_source.id
    )
    runner.db.add(job)
    runner.db.commit()
    
    total_created = 0
    total_updated = 0
    
    try:
        for query in queries:
            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={"current_query": query, "processed": queries.index(query) + 1, "total": len(queries)}
            )
            
            response = runner.query_perplexity(query)
            if response:
                content_items = runner.extract_content_from_response(response)
                results = runner.save_feed_items(content_items, data_source)
                total_created += results["created"]
                total_updated += results["updated"]
        
        # Update job record
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.items_created = total_created
        job.items_updated = total_updated
        runner.db.commit()
        
        return {
            "status": "completed",
            "created": total_created,
            "updated": total_updated,
            "queries_processed": len(queries)
        }
        
    except Exception as e:
        # Update job record with error
        job.status = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = str(e)
        runner.db.commit()
        
        raise self.retry(countdown=60, max_retries=3)
    
    finally:
        runner.db.close()

if __name__ == "__main__":
    # Test the runner
    runner = PerplexityRunner()
    result = runner.query_perplexity("What are the top technology news stories today?")
    print(json.dumps(result, indent=2)) 