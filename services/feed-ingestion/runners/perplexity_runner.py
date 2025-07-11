import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from dotenv import load_dotenv
from celery import group, chord
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from datetime import datetime

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from shared.database.connection import SessionLocal, engine
from shared.models.database_models import DataSource, FeedItem, IngestionJob, ContentCache, UserCategory, UserDB
from celery_app import celery_app

load_dotenv()

# In-memory Perplexity call history for debugging
# perplexity_call_history = []  # Each entry: {timestamp, category, prompt, response}
PERPLEXITY_HISTORY_LIMIT = 100

Base = declarative_base()

class PerplexityCallHistory(Base):
    __tablename__ = "perplexity_call_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    category = Column(String(140))
    prompt = Column(Text)
    response_word_count = Column(Integer)
    http_status_code = Column(Integer)
    response_content = Column(Text)  # Store full response text

# Ensure table exists (run at import)
Base.metadata.create_all(bind=engine)

def add_perplexity_history_db(category, prompt, response_word_count, http_status_code, response_content=""):
    print(f"[DEBUG] Attempting to log Perplexity call: category={category}, prompt={prompt[:60]}, response_word_count={response_word_count}, http_status_code={http_status_code}")
    db = SessionLocal()
    try:
        record = PerplexityCallHistory(
            timestamp=datetime.utcnow(),
            category=category,
            prompt=prompt,
            response_word_count=response_word_count,
            http_status_code=http_status_code,
            response_content=response_content
        )
        db.add(record)
        db.commit()
        print(f"[DEBUG] Successfully logged Perplexity call to DB (id={record.id})")
    except Exception as e:
        print(f"[ERROR] Failed to log Perplexity call: {e}")
    finally:
        db.close()

class PerplexityRunner:
    """Runner for Perplexity API integration"""
    
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.db = SessionLocal()
        
    def get_data_source(self) -> Optional[DataSource]:
        """Get or create Perplexity data source"""
        data_source = self.db.query(DataSource).filter(
            DataSource.name == "perplexity"
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name="perplexity",
                display_name="Perplexity AI",
                base_url=self.base_url,
                rate_limit_per_minute=60,
                config={"model": "sonar"}
            )
            self.db.add(data_source)
            self.db.commit()
            self.db.refresh(data_source)
        
        return data_source if data_source.is_active else None
    
    def get_user_categories(self, user_id: int) -> List[UserCategory]:
        """Get all active categories for a specific user"""
        return self.db.query(UserCategory).filter(
            UserCategory.user_id == user_id,
            UserCategory.is_active == True
        ).all()
    
    def generate_personalized_queries(self, user_categories: List[UserCategory]) -> List[str]:
        """Generate personalized queries based on user categories"""
        queries = []
        
        for category in user_categories:
            keywords = category.keywords or []
            category_name = category.category_name
            
            if keywords:
                # Create query using category keywords
                keyword_query = f"What are the latest news and developments about {', '.join(keywords)}?"
                queries.append({
                    "query": keyword_query,
                    "category_id": category.id,
                    "category_name": category_name,
                    "user_id": category.user_id
                })
            else:
                # Fallback to category name
                fallback_query = f"What are the latest news and developments in {category_name}?"
                queries.append({
                    "query": fallback_query,
                    "category_id": category.id,
                    "category_name": category_name,
                    "user_id": category.user_id
                })
        
        return queries
    
    def generate_fallback_queries(self) -> List[Dict[str, Any]]:
        """Generate fallback queries when no user categories are available"""
        fallback_queries = [
            "What are the top technology news stories today?",
            "What are the major world events happening right now?",
            "What are the latest developments in AI and machine learning?",
            "What are the trending topics in science and research?",
            "What are the key business and finance news today?"
        ]
        
        return [
            {
                "query": query,
                "category_id": None,
                "category_name": "General",
                "user_id": None
            }
            for query in fallback_queries
        ]
    
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
    
    def query_perplexity(self, query: str, model: str = "sonar", category: str = None) -> Optional[Dict]:
        print(f"[DEBUG] query_perplexity called with query='{query[:60]}', model='{model}', category='{category}'")
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
                    "content": "You are a helpful assistant that provides concise, informative summaries of current events and trending topics. Focus on factual information and provide relevant context. Respond in bullet points, but formatted as JSON with this exact structure: {\"news_items\": [{\"title\": \"Brief headline\", \"summary\": \"Detailed description\", \"url\": \"https://example.com\"}]}. Each news item should have a title (brief headline), summary (detailed description), and optionally a url (source link)."
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
            print(f"[DEBUG] Perplexity API response received: status_code={response.status_code}, response_keys={list(result.keys()) if isinstance(result, dict) else 'not_dict'}")
            
            # Cache the response
            self.cache_response(cache_key, result)
            
            # Add to PG call history for debugging
            word_count = 0
            response_content = ""
            if isinstance(result, dict):
                content = ""
                if "choices" in result and result["choices"]:
                    content = result["choices"][0]["message"]["content"]
                word_count = len(content.split())
                response_content = content
            add_perplexity_history_db(category, query, word_count, response.status_code, response_content)
            
            return result
            
        except requests.exceptions.RequestException as e:
            # Log failed call as well
            print(f"[DEBUG] Perplexity API request failed: {e}")
            error_content = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_content = e.response.text
                except:
                    error_content = str(e)
            add_perplexity_history_db(category, query, 0, getattr(e.response, 'status_code', None) or 0, error_content)
            print(f"Error querying Perplexity API: {e}")
            return None
    
    def extract_content_from_response(self, response: Dict) -> List[Dict[str, Any]]:
        """Extract structured content from Perplexity response - parse JSON format"""
        content_items = []
        
        try:
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]
                
                # Try to parse JSON response
                try:
                    import json
                    parsed_content = json.loads(content)
                    
                    # Extract news items from JSON
                    if isinstance(parsed_content, dict) and "news_items" in parsed_content:
                        news_items = parsed_content["news_items"]
                        if isinstance(news_items, list):
                            for item in news_items:
                                if isinstance(item, dict):
                                    content_items.append({
                                        "title": item.get("title", "Untitled"),
                                        "summary": item.get("summary", ""),
                                        "url": item.get("url", ""),
                                        "source": "Perplexity AI"
                                    })
                    elif isinstance(parsed_content, list):
                        # Direct array of items
                        for item in parsed_content:
                            if isinstance(item, dict):
                                content_items.append({
                                    "title": item.get("title", "Untitled"),
                                    "summary": item.get("summary", ""),
                                    "url": item.get("url", ""),
                                    "source": "Perplexity AI"
                                })
                    
                    print(f"[DEBUG] Successfully parsed {len(content_items)} JSON news items")
                    
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] Failed to parse JSON response: {e}")
                    print(f"[DEBUG] Raw content: {content[:200]}...")
                    # Fallback to old parsing if JSON fails
                    content_items = self._fallback_parse_content(content)
            
        except Exception as e:
            print(f"Error extracting content from response: {e}")
        
        return content_items
    
    def _fallback_parse_content(self, content: str) -> List[Dict[str, Any]]:
        """Fallback parsing for non-JSON responses"""
        content_items = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 20:  # Reasonable length for a news item
                content_items.append({
                    "title": line[:100] + "..." if len(line) > 100 else line,
                    "summary": line,
                    "url": "",
                    "source": "Perplexity AI"
                })
        
        return content_items
    
    def save_feed_items(self, content_items: List[Dict], data_source: DataSource, category_info: Dict[str, Any] = None) -> Dict[str, int]:
        """Save extracted content as feed items with category association"""
        created = 0
        updated = 0
        
        category_name = category_info.get("category_name", "General") if category_info else "General"
        category_id = category_info.get("category_id") if category_info else None
        user_id = category_info.get("user_id") if category_info else None
        
        # Delete ALL existing items for this category before inserting new ones
        if content_items:
            try:
                # Delete all items for this category (not just old ones)
                deleted_count = self.db.query(FeedItem).filter(
                    FeedItem.category == category_name
                ).delete()
                print(f"Deleted {deleted_count} existing items for category '{category_name}' before inserting new ones")
            except Exception as e:
                print(f"Error deleting existing items for category {category_name}: {e}")
        
        for item in content_items:
            try:
                # Create new item with category association
                feed_item = FeedItem(
                    title=item.get("title", "Untitled"),
                    summary=item.get("summary", ""),
                    url=item.get("url", ""),
                    source="Perplexity AI",
                    data_source_id=data_source.id,
                    published_at=datetime.utcnow(),
                    raw_data=item,
                    category=category_name,
                    tags=["ai", "perplexity", category_name.lower()] if category_name != "General" else ["ai", "perplexity"]
                )
                
                # Add user-specific metadata if available
                if user_id:
                    feed_item.raw_data = {
                        **item,
                        "user_category_id": category_id,
                        "user_id": user_id,
                        "category_name": category_name
                    }
                
                self.db.add(feed_item)
                created += 1
                
            except Exception as e:
                print(f"Error saving feed item: {e}")
                continue
        
        self.db.commit()
        return {"created": created, "updated": updated}

    def create_ingestion_job_record(self, job_type):
        from shared.database.connection import SessionLocal
        from shared.models.database_models import IngestionJob
        db = SessionLocal()
        job = IngestionJob(
            job_type=job_type,
            status="running",
            started_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        job_id = job.id
        db.close()
        return job_id

@celery_app.task(bind=True)
def ingest_perplexity(self, user_id: Optional[int] = None, queries: List[Dict[str, Any]] = None):
    """Celery task for Perplexity ingestion with personalized queries"""
    runner = PerplexityRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("Perplexity data source not found or inactive")
        return {"error": "Data source not found"}
    
    # Generate queries based on user categories or use fallback
    if queries is None:
        if user_id:
            # Get personalized queries for specific user
            user_categories = runner.get_user_categories(user_id)
            if user_categories:
                queries = runner.generate_personalized_queries(user_categories)
                print(f"Generated {len(queries)} personalized queries for user {user_id}")
            else:
                # No user categories, use fallback
                queries = runner.generate_fallback_queries()
                print(f"No user categories found for user {user_id}, using fallback queries")
        else:
            # No user specified, use fallback
            queries = runner.generate_fallback_queries()
            print("No user specified, using fallback queries")
    
    # Create ingestion job record
    job = IngestionJob(
        job_type="perplexity",
        status="running",
        started_at=datetime.utcnow(),
        parameters={"user_id": user_id, "queries": [q.get("query", q) if isinstance(q, dict) else q for q in queries]},
        data_source_id=data_source.id
    )
    runner.db.add(job)
    runner.db.commit()
    
    total_created = 0
    total_updated = 0
    
    try:
        for i, query_info in enumerate(queries):
            if isinstance(query_info, dict):
                query = query_info["query"]
                category_info = query_info
            else:
                query = query_info
                category_info = {"category_name": "General", "category_id": None, "user_id": None}
            
            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "current_query": query, 
                    "processed": i + 1, 
                    "total": len(queries),
                    "category": category_info.get("category_name", "General")
                }
            )
            
            response = runner.query_perplexity(query, category=category_info.get("category_name"))
            if response:
                content_items = runner.extract_content_from_response(response)
                results = runner.save_feed_items(content_items, data_source, category_info)
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
            "queries_processed": len(queries),
            "user_id": user_id
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

@celery_app.task(bind=True)
def aggregate_perplexity_results(self, results, job_id, total_users):
    """Callback to aggregate results from all user ingestions and update the job record."""
    from shared.database.connection import SessionLocal
    from shared.models.database_models import IngestionJob
    db = SessionLocal()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    total_created = 0
    total_updated = 0
    users_processed = 0
    for user_result in results:
        if user_result and "created" in user_result:
            total_created += user_result["created"]
            total_updated += user_result["updated"]
            users_processed += 1
    if job:
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.items_created = total_created
        job.items_updated = total_updated
        db.commit()
    db.close()
    return {
        "status": "completed",
        "created": total_created,
        "updated": total_updated,
        "users_processed": users_processed,
        "total_users": total_users
    }

@celery_app.task(bind=True)
def ingest_perplexity_for_all_users(self):
    """Celery task for Perplexity ingestion for all users with categories"""
    runner = PerplexityRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("Perplexity data source not found or inactive")
        return {"error": "Data source not found"}
    
    # Get all user IDs with categories (explicit join)
    user_id_rows = runner.db.query(UserDB.id).join(
        UserCategory, UserDB.id == UserCategory.user_id
    ).filter(
        UserCategory.is_active == True
    ).distinct().all()
    user_ids = [user_id for (user_id,) in user_id_rows]
    
    if not user_ids:
        print("No users with active categories found.")
        return {"status": "no_users"}
    
    # Create a group of ingestion tasks for all user IDs
    tasks = [ingest_perplexity.s(user_id) for user_id in user_ids]
    job_id = runner.create_ingestion_job_record("perplexity_all_users")
    chord(group(tasks), aggregate_perplexity_results.s(job_id, len(user_ids))).apply_async()
    print(f"Triggered Perplexity ingestion for {len(user_ids)} users (job_id={job_id})")
    return {"status": "started", "users": len(user_ids), "job_id": job_id}

if __name__ == "__main__":
    # Test the runner
    runner = PerplexityRunner()
    result = runner.query_perplexity("What are the top technology news stories today?")
    print(json.dumps(result, indent=2)) 

# Add FastAPI debug endpoint if this file is run as main or imported in a FastAPI app
try:
    from fastapi import APIRouter
    router = APIRouter()
    @router.get("/debug/perplexity-history")
    async def get_perplexity_history():
        db = SessionLocal()
        try:
            records = db.query(PerplexityCallHistory).order_by(PerplexityCallHistory.timestamp.desc()).limit(100).all()
            return [
                {
                    'timestamp': r.timestamp.isoformat() + 'Z',
                    'category': r.category,
                    'prompt': r.prompt,
                    'response_word_count': r.response_word_count,
                    'http_status_code': r.http_status_code,
                    'response_content': r.response_content
                }
                for r in records
            ]
        finally:
            db.close()
except ImportError:
    pass 