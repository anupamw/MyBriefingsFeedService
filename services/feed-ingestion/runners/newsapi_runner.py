import os
import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from shared.database.connection import SessionLocal, engine
from shared.models.database_models import DataSource, FeedItem, IngestionJob
from celery_app import celery_app

load_dotenv()

# In-memory NewsAPI call history for debugging
NEWSAPI_HISTORY_LIMIT = 100

Base = declarative_base()

class NewsAPICallHistory(Base):
    __tablename__ = "newsapi_call_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    endpoint = Column(String(140))
    category = Column(String(140))
    country = Column(String(10))
    response_status_code = Column(Integer)
    articles_found = Column(Integer)
    articles_saved = Column(Integer)
    error_message = Column(Text, nullable=True)
    response_content = Column(Text, nullable=True)  # Store response text for debugging

# Ensure table exists (run at import)
Base.metadata.create_all(bind=engine)

def add_newsapi_history_db(endpoint, category, country, response_status_code, articles_found, articles_saved, error_message=None, response_content=None):
    print(f"[DEBUG] Attempting to log NewsAPI call: endpoint={endpoint}, category={category}, country={country}, status={response_status_code}, articles_found={articles_found}, articles_saved={articles_saved}")
    db = SessionLocal()
    try:
        record = NewsAPICallHistory(
            timestamp=datetime.utcnow(),
            endpoint=endpoint,
            category=category,
            country=country,
            response_status_code=response_status_code,
            articles_found=articles_found,
            articles_saved=articles_saved,
            error_message=error_message,
            response_content=response_content
        )
        db.add(record)
        db.commit()
        print(f"[DEBUG] Successfully logged NewsAPI call to DB (id={record.id})")
    except Exception as e:
        print(f"[ERROR] Failed to log NewsAPI call: {e}")
    finally:
        db.close()

class NewsAPIRunner:
    """Runner for NewsAPI integration"""
    
    def __init__(self):
        self.api_key = os.getenv("NEWS_API_KEY")
        self.base_url = "https://newsapi.org/v2"
        self.db = SessionLocal()
        
    def get_data_source(self) -> Optional[DataSource]:
        """Get or create NewsAPI data source"""
        data_source = self.db.query(DataSource).filter(
            DataSource.name == "newsapi"
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name="newsapi",
                display_name="NewsAPI",
                base_url=self.base_url,
                rate_limit_per_minute=60,
                config={"api_key_required": True}
            )
            self.db.add(data_source)
            self.db.commit()
            self.db.refresh(data_source)
        
        return data_source if data_source.is_active else None
    
    def get_top_headlines(self, category: str = "general", country: str = "us", page_size: int = 20) -> List[Dict]:
        """Get top headlines from NewsAPI"""
        if not self.api_key:
            print("NEWS_API_KEY not found in environment")
            return []
        
        url = f"{self.base_url}/top-headlines"
        params = {
            "apiKey": self.api_key,
            "category": category,
            "country": country,
            "pageSize": page_size
        }
        
        print(f"[DEBUG] Fetching NewsAPI top headlines: category={category}, country={country}")
        
        try:
            response = requests.get(url, params=params, timeout=30)
            print(f"[DEBUG] NewsAPI response status: {response.status_code}")
            
            articles = []
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok" and "articles" in data:
                    articles = data["articles"]
                    print(f"[DEBUG] Found {len(articles)} articles from NewsAPI")
                    
                    # Log successful API call
                    add_newsapi_history_db(
                        endpoint="top-headlines",
                        category=category,
                        country=country,
                        response_status_code=response.status_code,
                        articles_found=len(articles),
                        articles_saved=0,  # Will be updated when saved
                        response_content=response.text[:1000] if response.text else None
                    )
                else:
                    print(f"[DEBUG] NewsAPI error response: {data}")
                    add_newsapi_history_db(
                        endpoint="top-headlines",
                        category=category,
                        country=country,
                        response_status_code=response.status_code,
                        articles_found=0,
                        articles_saved=0,
                        error_message=str(data),
                        response_content=response.text[:1000] if response.text else None
                    )
            else:
                print(f"[DEBUG] NewsAPI HTTP error: {response.status_code} - {response.text}")
                add_newsapi_history_db(
                    endpoint="top-headlines",
                    category=category,
                    country=country,
                    response_status_code=response.status_code,
                    articles_found=0,
                    articles_saved=0,
                    error_message=response.text[:500] if response.text else "HTTP Error",
                    response_content=response.text[:1000] if response.text else None
                )
                
        except Exception as e:
            print(f"[ERROR] NewsAPI request failed: {e}")
            add_newsapi_history_db(
                endpoint="top-headlines",
                category=category,
                country=country,
                response_status_code=0,
                articles_found=0,
                articles_saved=0,
                error_message=str(e),
                response_content=""
            )
        
        return articles
    
    def search_news(self, query: str, language: str = "en", sort_by: str = "publishedAt", page_size: int = 20) -> List[Dict]:
        """Search for news articles using NewsAPI"""
        if not self.api_key:
            print("NEWS_API_KEY not found in environment")
            return []
        
        url = f"{self.base_url}/everything"
        params = {
            "apiKey": self.api_key,
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "pageSize": page_size
        }
        
        print(f"[DEBUG] Searching NewsAPI: query='{query}', language={language}")
        
        try:
            response = requests.get(url, params=params, timeout=30)
            print(f"[DEBUG] NewsAPI search response status: {response.status_code}")
            
            articles = []
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok" and "articles" in data:
                    articles = data["articles"]
                    print(f"[DEBUG] Found {len(articles)} articles from NewsAPI search")
                    
                    # Log successful API call
                    add_newsapi_history_db(
                        endpoint="everything",
                        category=query,
                        country="",
                        response_status_code=response.status_code,
                        articles_found=len(articles),
                        articles_saved=0,
                        response_content=response.text[:1000] if response.text else None
                    )
                else:
                    print(f"[DEBUG] NewsAPI search error response: {data}")
                    add_newsapi_history_db(
                        endpoint="everything",
                        category=query,
                        country="",
                        response_status_code=response.status_code,
                        articles_found=0,
                        articles_saved=0,
                        error_message=str(data),
                        response_content=response.text[:1000] if response.text else None
                    )
            else:
                print(f"[DEBUG] NewsAPI search HTTP error: {response.status_code} - {response.text}")
                add_newsapi_history_db(
                    endpoint="everything",
                    category=query,
                    country="",
                    response_status_code=response.status_code,
                    articles_found=0,
                    articles_saved=0,
                    error_message=response.text[:500] if response.text else "HTTP Error",
                    response_content=response.text[:1000] if response.text else None
                )
                
        except Exception as e:
            print(f"[ERROR] NewsAPI search request failed: {e}")
            add_newsapi_history_db(
                endpoint="everything",
                category=query,
                country="",
                response_status_code=0,
                articles_found=0,
                articles_saved=0,
                error_message=str(e),
                response_content=""
            )
        
        return articles
    
    def extract_image_url(self, article: Dict) -> Optional[str]:
        """Extract image URL from NewsAPI article"""
        # Try different image fields in order of preference
        image_fields = [
            "urlToImage",  # Main article image
            "url",  # Fallback to article URL
        ]
        
        for field in image_fields:
            if field in article and article[field]:
                return article[field]
        
        return None
    

    
    def save_feed_items(self, articles: List[Dict], data_source: DataSource, category_info: Dict[str, Any] = None) -> Dict[str, int]:
        """Save NewsAPI articles as feed items"""
        created = 0
        updated = 0
        
        category_name = category_info.get("category_name", "General News") if category_info else "General News"
        category_id = category_info.get("category_id") if category_info else None
        user_id = category_info.get("user_id") if category_info else None
        
        print(f"[DEBUG] Starting to save {len(articles)} NewsAPI articles for category '{category_name}'")
        
        # Use all articles for now - let the user decide relevance
        # The short_summary should already provide better search results
        filtered_articles = articles
        print(f"[DEBUG] Using {len(filtered_articles)} articles for category '{category_name}'")
        
        for article in filtered_articles:
            try:
                # Extract image URL
                image_url = self.extract_image_url(article)
                
                # Parse publication date
                published_at = datetime.utcnow()
                if article.get("publishedAt"):
                    try:
                        published_at = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
                    except:
                        published_at = datetime.utcnow()
                
                # Create feed item
                feed_item = FeedItem(
                    title=article.get("title", "Untitled")[:500],  # Truncate to fit DB field
                    summary=article.get("description", ""),
                    content=article.get("content", ""),
                    url=article.get("url", ""),
                    image_url=image_url,  # NEW: Store image URL
                    source=f"NewsAPI - {article.get('source', {}).get('name', 'Unknown')}",
                    data_source_id=data_source.id,
                    published_at=published_at,
                    raw_data=article,
                    category=category_name,
                    tags=["newsapi", category_name.lower(), "news"]
                )
                
                # Add user-specific metadata if available
                if user_id:
                    feed_item.raw_data = {
                        **article,
                        "user_category_id": category_id,
                        "user_id": user_id,
                        "category_name": category_name,
                        "image_url": image_url
                    }
                
                self.db.add(feed_item)
                created += 1
                
                print(f"[DEBUG] Added NewsAPI article: '{feed_item.title[:50]}...' with image: {image_url is not None}")
                
            except Exception as e:
                print(f"[ERROR] Error saving NewsAPI article: {e}")
                continue
        
        try:
            self.db.commit()
            print(f"[DEBUG] Successfully committed {created} NewsAPI articles to database")
            
            # Update the history record with actual saved count
            if created > 0:
                # Find the most recent history record for this category and update it
                recent_record = self.db.query(NewsAPICallHistory).filter(
                    NewsAPICallHistory.category == category_name
                ).order_by(NewsAPICallHistory.timestamp.desc()).first()
                
                if recent_record:
                    recent_record.articles_saved = created
                    self.db.commit()
            
        except Exception as e:
            print(f"[ERROR] Error committing to database: {e}")
            self.db.rollback()
            return {"created": 0, "updated": 0, "error": str(e)}
        
        return {"created": created, "updated": updated}

@celery_app.task(bind=True)
def ingest_newsapi_headlines(self, categories: List[str] = None, countries: List[str] = None):
    """Celery task for NewsAPI headlines ingestion"""
    runner = NewsAPIRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("NewsAPI data source not found or inactive")
        return {"error": "Data source not found"}
    
    if not categories:
        categories = ["general", "technology", "business", "sports", "entertainment"]
    
    if not countries:
        countries = ["us", "gb", "in"]  # US, UK, India
    
    print(f"[DEBUG] NewsAPI headlines ingestion started with categories: {categories}, countries: {countries}")
    
    total_created = 0
    
    try:
        for country in countries:
            for category in categories:
                # Update task progress
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current_category": category,
                        "current_country": country,
                        "processed": f"{country}-{category}",
                        "total": f"{len(countries)} countries x {len(categories)} categories"
                    }
                )
                
                articles = runner.get_top_headlines(category=category, country=country, page_size=10)
                if articles:
                    results = runner.save_feed_items(articles, data_source, {"category_name": f"{category.title()} News"})
                    total_created += results["created"]
                    print(f"[DEBUG] Saved {results['created']} articles for {category} in {country}")
                
                # Add delay to respect rate limits
                time.sleep(1)
        
        return {
            "status": "completed",
            "created": total_created,
            "categories_processed": len(categories),
            "countries_processed": len(countries)
        }
        
    except Exception as e:
        print(f"[ERROR] NewsAPI headlines ingestion failed: {e}")
        raise self.retry(countdown=60, max_retries=3)
    
    finally:
        runner.db.close()

@celery_app.task(bind=True)
def ingest_newsapi_search(self, queries: List[str] = None):
    """Celery task for NewsAPI search ingestion"""
    runner = NewsAPIRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("NewsAPI data source not found or inactive")
        return {"error": "Data source not found"}
    
    if not queries:
        queries = ["artificial intelligence", "climate change", "space exploration", "renewable energy"]
    
    print(f"[DEBUG] NewsAPI search ingestion started with queries: {queries}")
    
    total_created = 0
    
    try:
        for i, query in enumerate(queries):
            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "current_query": query,
                    "processed": i + 1,
                    "total": len(queries)
                }
            )
            
            articles = runner.search_news(query=query, page_size=10)
            if articles:
                results = runner.save_feed_items(articles, data_source, {"category_name": f"{query.title()} News"})
                total_created += results["created"]
                print(f"[DEBUG] Saved {results['created']} articles for query '{query}'")
            
            # Add delay to respect rate limits
            time.sleep(1)
        
        return {
            "status": "completed",
            "created": total_created,
            "queries_processed": len(queries)
        }
        
    except Exception as e:
        print(f"[ERROR] NewsAPI search ingestion failed: {e}")
        raise self.retry(countdown=60, max_retries=3)
    
    finally:
        runner.db.close()

@celery_app.task(bind=True)
def ingest_newsapi_for_user(self, user_id: int):
    """Trigger NewsAPI ingestion for a specific user based on their categories"""
    from shared.models.database_models import UserCategory
    import json
    
    runner = NewsAPIRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("NewsAPI data source not found or inactive")
        return {"error": "Data source not found"}
    
    db = SessionLocal()
    user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    
    if not user_categories:
        db.close()
        return {"status": "no_categories", "user_id": user_id}
    
    total_created = 0
    
    try:
        for user_category in user_categories:
            category_name = user_category.category_name
            
            # Search for news related to the user's category
            articles = runner.search_news(query=category_name, page_size=15)
            if articles:
                results = runner.save_feed_items(
                    articles, 
                    data_source, 
                    {
                        "category_name": category_name,
                        "category_id": user_category.id,
                        "user_id": user_id
                    }
                )
                total_created += results["created"]
                print(f"[DEBUG] Saved {results['created']} NewsAPI articles for user {user_id}, category '{category_name}'")
            
            # Add delay to respect rate limits
            time.sleep(1)
        
        return {
            "status": "completed",
            "created": total_created,
            "user_id": user_id,
            "categories_processed": len(user_categories)
        }
        
    except Exception as e:
        print(f"[ERROR] NewsAPI user ingestion failed: {e}")
        return {"error": str(e)}
    
    finally:
        db.close()
        runner.db.close()

@celery_app.task(bind=True)
def ingest_newsapi_for_all_users(self):
    """Trigger NewsAPI ingestion for all users with categories"""
    from shared.models.database_models import UserCategory
    
    runner = NewsAPIRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("NewsAPI data source not found or inactive")
        return {"error": "Data source not found"}
    
    db = SessionLocal()
    
    # Get all users with categories
    user_categories = db.query(UserCategory).filter(
        UserCategory.is_active == True
    ).all()
    
    if not user_categories:
        db.close()
        return {"status": "no_users_with_categories"}
    
    # Group categories by user
    users_with_categories = {}
    for user_cat in user_categories:
        if user_cat.user_id not in users_with_categories:
            users_with_categories[user_cat.user_id] = []
        users_with_categories[user_cat.user_id].append(user_cat)
    
    total_created = 0
    users_processed = 0
    
    try:
        for user_id, categories in users_with_categories.items():
            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "current_user": user_id,
                    "processed": users_processed + 1,
                    "total": len(users_with_categories)
                }
            )
            
            for user_category in categories:
                category_name = user_category.category_name
                
                # Search for news related to the user's category
                articles = runner.search_news(query=category_name, page_size=10)
                if articles:
                    results = runner.save_feed_items(
                        articles, 
                        data_source, 
                        {
                            "category_name": category_name,
                            "category_id": user_category.id,
                            "user_id": user_id
                        }
                    )
                    total_created += results["created"]
                    print(f"[DEBUG] Saved {results['created']} NewsAPI articles for user {user_id}, category '{category_name}'")
                
                # Add delay to respect rate limits
                time.sleep(1)
            
            users_processed += 1
        
        return {
            "status": "completed",
            "created": total_created,
            "users_processed": users_processed,
            "total_users": len(users_with_categories)
        }
        
    except Exception as e:
        print(f"[ERROR] NewsAPI all users ingestion failed: {e}")
        raise self.retry(countdown=60, max_retries=3)
    
    finally:
        db.close()
        runner.db.close()

# Add FastAPI debug endpoint if this file is run as main or imported in a FastAPI app
try:
    from fastapi import APIRouter
    router = APIRouter()
    
    @router.get("/debug/newsapi-history")
    async def get_newsapi_history():
        db = SessionLocal()
        try:
            records = db.query(NewsAPICallHistory).order_by(NewsAPICallHistory.timestamp.desc()).limit(100).all()
            return [
                {
                    'timestamp': r.timestamp.isoformat() + 'Z',
                    'endpoint': r.endpoint,
                    'category': r.category,
                    'country': r.country,
                    'response_status_code': r.response_status_code,
                    'articles_found': r.articles_found,
                    'articles_saved': r.articles_saved,
                    'error_message': r.error_message,
                    'response_content': r.response_content
                }
                for r in records
            ]
        finally:
            db.close()
except ImportError:
    pass

if __name__ == "__main__":
    # Test the runner
    runner = NewsAPIRunner()
    articles = runner.get_top_headlines(category="technology", country="us", page_size=5)
    print(f"Found {len(articles)} technology articles")
    for article in articles:
        print(f"- {article.get('title', 'No title')}")
        print(f"  Image: {article.get('urlToImage', 'No image')}") 