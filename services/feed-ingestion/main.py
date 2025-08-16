from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
import json
import requests

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
from shared.database.connection import SessionLocal, init_database
from shared.models.database_models import DataSource, FeedItem, IngestionJob, UserCategory, UserDB
from runners.perplexity_runner import PerplexityRunner, router as perplexity_debug_router
from runners.reddit_runner import RedditRunner, router as reddit_debug_router
from runners.social_runner import SocialRunner
from runners.newsapi_runner import NewsAPIRunner, router as newsapi_debug_router

load_dotenv()

app = FastAPI(
    title="Feed Ingestion Service",
    description="A service for ingesting and processing feed data from various sources",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class DataSourceCreate(BaseModel):
    name: str
    display_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    rate_limit_per_minute: int = 60
    config: Optional[Dict[str, Any]] = None

class DataSourceResponse(BaseModel):
    id: int
    name: str
    display_name: str
    base_url: Optional[str] = None
    rate_limit_per_minute: int
    is_active: bool
    last_used: Optional[str] = None
    created_at: str
    updated_at: str

class IngestionJobResponse(BaseModel):
    id: int
    job_type: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    items_processed: int
    items_created: int
    items_updated: int
    created_at: str

class FeedItemResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    created_at: str
    category: Optional[str] = None
    engagement_score: Optional[float] = None
    tags: Optional[List[str]] = None

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def parse_tags(tags_data):
    """Parse tags from database, handling both JSON strings and lists"""
    if tags_data is None:
        return []
    if isinstance(tags_data, list):
        return tags_data
    if isinstance(tags_data, str):
        try:
            return json.loads(tags_data)
        except (json.JSONDecodeError, TypeError):
            return []
    return []

# Helper function for UTC ISO string with 'Z'
def to_utc_z(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace('+00:00', 'Z')

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup. (Ingestion on startup is now disabled.)"""
    init_database()
    # The following code is commented out to prevent triggering a full ingestion for all users on every pod restart.
    # This is no longer needed as periodic ingestion is handled by Celery Beat.
    # try:
    #     from celery_app import celery_app
    #     celery_app.send_task("runners.perplexity_runner.ingest_perplexity_for_all_users")
    #     print("Triggered full Perplexity ingestion for all users on startup.")
    # except Exception as e:
    #     print(f"Failed to trigger full ingestion on startup: {e}")

@app.get("/ingestion/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "Feed Ingestion Service",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/data-sources", response_model=List[DataSourceResponse])
async def get_data_sources(db: SessionLocal = Depends(get_db)):
    """Get all data sources"""
    sources = db.query(DataSource).all()
    return [
        DataSourceResponse(
            id=source.id,
            name=source.name,
            display_name=source.display_name,
            base_url=source.base_url,
            rate_limit_per_minute=source.rate_limit_per_minute,
            is_active=source.is_active,
            last_used=to_utc_z(source.last_used),
            created_at=to_utc_z(source.created_at),
            updated_at=to_utc_z(source.updated_at)
        )
        for source in sources
    ]

@app.post("/data-sources", response_model=DataSourceResponse)
async def create_data_source(source: DataSourceCreate, db: SessionLocal = Depends(get_db)):
    """Create a new data source"""
    # Check if source already exists
    existing = db.query(DataSource).filter(DataSource.name == source.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Data source already exists")
    
    db_source = DataSource(
        name=source.name,
        display_name=source.display_name,
        api_key=source.api_key,
        base_url=source.base_url,
        rate_limit_per_minute=source.rate_limit_per_minute,
        config=source.config
    )
    
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    
    return DataSourceResponse(
        id=db_source.id,
        name=db_source.name,
        display_name=db_source.display_name,
        base_url=db_source.base_url,
        rate_limit_per_minute=db_source.rate_limit_per_minute,
        is_active=db_source.is_active,
        last_used=to_utc_z(db_source.last_used),
        created_at=to_utc_z(db_source.created_at),
        updated_at=to_utc_z(db_source.updated_at)
    )

@app.put("/data-sources/{source_id}/toggle")
async def toggle_data_source(source_id: int, db: SessionLocal = Depends(get_db)):
    """Toggle data source active status"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    source.is_active = not source.is_active
    db.commit()
    
    return {"message": f"Data source {source.name} {'activated' if source.is_active else 'deactivated'}"}

@app.get("/ingestion-jobs", response_model=List[IngestionJobResponse])
async def get_ingestion_jobs(
    limit: int = 50, 
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    db: SessionLocal = Depends(get_db)
):
    """Get ingestion jobs with optional filtering"""
    query = db.query(IngestionJob)
    
    if job_type:
        query = query.filter(IngestionJob.job_type == job_type)
    if status:
        query = query.filter(IngestionJob.status == status)
    
    jobs = query.order_by(IngestionJob.created_at.desc()).limit(limit).all()
    
    return [
        IngestionJobResponse(
            id=job.id,
            job_type=job.job_type,
            status=job.status,
            started_at=to_utc_z(job.started_at),
            completed_at=to_utc_z(job.completed_at),
            error_message=job.error_message,
            items_processed=job.items_processed,
            items_created=job.items_created,
            items_updated=job.items_updated,
            created_at=to_utc_z(job.created_at)
        )
        for job in jobs
    ]

@app.post("/ingest/perplexity")
async def trigger_perplexity_ingestion(
    user_id: Optional[int] = None,
    queries: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None
):
    """Trigger Perplexity ingestion job (personalized or general)"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.perplexity_runner.ingest_perplexity",
            args=[user_id, queries]
        )
        
        return {
            "message": "Perplexity ingestion job started",
            "task_id": task.id,
            "status": "pending",
            "user_id": user_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion job: {str(e)}")

@app.post("/ingest/perplexity/all-users")
async def trigger_perplexity_ingestion_all_users(background_tasks: BackgroundTasks = None):
    """Trigger Perplexity ingestion for all users with categories"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.perplexity_runner.ingest_perplexity_for_all_users"
        )
        
        return {
            "message": "Perplexity ingestion for all users started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion job: {str(e)}")

@app.post("/ingest/reddit")
async def trigger_reddit_ingestion(
    subreddits: Optional[List[str]] = None,
    time_filter: str = "day"
):
    """Trigger Reddit ingestion job"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.reddit_runner.ingest_reddit",
            args=[subreddits, time_filter]
        )
        
        return {
            "message": "Reddit ingestion job started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion job: {str(e)}")

@app.post("/ingest/reddit/user/{user_id}")
async def trigger_reddit_ingestion_for_user(user_id: int):
    """Trigger Reddit ingestion for a specific user based on their categories"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.reddit_runner.ingest_reddit_for_user",
            args=[user_id]
        )
        
        return {
            "message": f"Reddit ingestion for user {user_id} started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Reddit ingestion for user: {str(e)}")

@app.post("/ingest/reddit/all-users")
async def trigger_reddit_ingestion_all_users():
    """Trigger Reddit ingestion for all users based on their categories"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.reddit_runner.ingest_reddit_for_all_users"
        )
        
        return {
            "message": "Reddit ingestion for all users started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Reddit ingestion for all users: {str(e)}")

@app.post("/ingest/social")
async def trigger_social_ingestion(sources: Optional[List[str]] = None):
    """Trigger social media ingestion job"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.social_runner.ingest_social",
            args=[sources]
        )
        
        return {
            "message": "Social media ingestion job started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion job: {str(e)}")

@app.post("/ingest/newsapi/headlines")
async def trigger_newsapi_headlines_ingestion(request: Request):
    """Trigger NewsAPI headlines ingestion job"""
    try:
        # Parse request body
        body = await request.json()
        categories = body.get("categories") if body else None
        countries = body.get("countries") if body else None
        
        # Submit Celery task
        task = celery_app.send_task(
            "runners.newsapi_runner.ingest_newsapi_headlines",
            args=[categories, countries]
        )
        
        return {
            "message": "NewsAPI headlines ingestion job started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start NewsAPI headlines ingestion: {str(e)}")

@app.post("/ingest/newsapi/search")
async def trigger_newsapi_search_ingestion(request: Request):
    """Trigger NewsAPI search ingestion job"""
    try:
        # Parse request body
        body = await request.json()
        queries = body.get("queries") if body else None
        
        # Submit Celery task
        task = celery_app.send_task(
            "runners.newsapi_runner.ingest_newsapi_search",
            args=[queries]
        )
        
        return {
            "message": "NewsAPI search ingestion job started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start NewsAPI search ingestion: {str(e)}")

@app.post("/ingest/newsapi/user/{user_id}")
async def trigger_newsapi_ingestion_for_user(user_id: int):
    """Trigger NewsAPI ingestion for a specific user based on their categories"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.newsapi_runner.ingest_newsapi_for_user",
            args=[user_id]
        )
        
        return {
            "message": f"NewsAPI ingestion for user {user_id} started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start NewsAPI ingestion for user: {str(e)}")

@app.post("/ingest/newsapi/all-users")
async def trigger_newsapi_ingestion_all_users(background_tasks: BackgroundTasks = None):
    """Trigger NewsAPI ingestion for all users with categories"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "runners.newsapi_runner.ingest_newsapi_for_all_users"
        )
        
        return {
            "message": "NewsAPI ingestion for all users started",
            "task_id": task.id,
            "status": "pending"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start NewsAPI ingestion for all users: {str(e)}")

@app.get("/feed-items", response_model=List[FeedItemResponse])
async def get_feed_items(
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    source: Optional[str] = None,
    user_id: Optional[int] = None,
    db: SessionLocal = Depends(get_db)
):
    """Get feed items with optional filtering"""
    query = db.query(FeedItem)
    
    if category:
        query = query.filter(FeedItem.category == category)
    if source:
        query = query.filter(FeedItem.source == source)
    
    # Filter by user if specified
    if user_id:
        # Get user's categories
        user_categories = db.query(UserCategory).filter(
            UserCategory.user_id == user_id,
            UserCategory.is_active == True
        ).all()
        
        if user_categories:
            category_names = [cat.category_name for cat in user_categories]
            query = query.filter(FeedItem.category.in_(category_names))
    
    items = query.order_by(FeedItem.published_at.desc()).offset(offset).limit(limit).all()
    
    return [
        FeedItemResponse(
            id=item.id,
            title=item.title,
            summary=item.summary,
            content=item.content,
            url=item.url,
            image_url=item.image_url,
            source=item.source,
            published_at=to_utc_z(item.published_at),
            created_at=to_utc_z(item.created_at),
            category=item.category,
            engagement_score=item.engagement_score,
            tags=parse_tags(item.tags)
        )
        for item in items
    ]

@app.get("/feed-items/user/{user_id}", response_model=List[FeedItemResponse])
async def get_user_feed_items(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    db: SessionLocal = Depends(get_db)
):
    """Get personalized feed items for a specific user"""
    # Get user's categories
    user_categories = db.query(UserCategory).filter(
        UserCategory.user_id == user_id,
        UserCategory.is_active == True
    ).all()
    
    if not user_categories:
        # Return general items if no categories
        items = db.query(FeedItem).filter(
            FeedItem.category == "General"
        ).order_by(FeedItem.published_at.desc()).offset(offset).limit(limit).all()
    else:
        # Get items matching user's categories
        category_names = [cat.category_name for cat in user_categories]
        items = db.query(FeedItem).filter(
            FeedItem.category.in_(category_names)
        ).order_by(FeedItem.published_at.desc()).offset(offset).limit(limit).all()
    
    return [
        FeedItemResponse(
            id=item.id,
            title=item.title,
            summary=item.summary,
            content=item.content,
            url=item.url,
            image_url=item.image_url,
            source=item.source,
            published_at=to_utc_z(item.published_at),
            created_at=to_utc_z(item.created_at),
            category=item.category,
            engagement_score=item.engagement_score,
            tags=parse_tags(item.tags)
        )
        for item in items
    ]

@app.get("/user-categories/{user_id}")
async def get_user_categories(user_id: int, db: SessionLocal = Depends(get_db)):
    """Get categories for a specific user"""
    categories = db.query(UserCategory).filter(
        UserCategory.user_id == user_id,
        UserCategory.is_active == True
    ).all()
    
    return [
        {
            "id": cat.id,
            "category_name": cat.category_name,
            "keywords": cat.keywords or [],
            "sources": cat.sources or [],
            "created_at": to_utc_z(cat.created_at)
        }
        for cat in categories
    ]

@app.get("/stats")
async def get_ingestion_stats(db: SessionLocal = Depends(get_db)):
    """Get ingestion statistics"""
    total_items = db.query(FeedItem).count()
    total_jobs = db.query(IngestionJob).count()
    active_sources = db.query(DataSource).filter(DataSource.is_active == True).count()
    
    # Get recent job stats
    recent_jobs = db.query(IngestionJob).filter(
        IngestionJob.created_at >= datetime.utcnow() - timedelta(days=7)
    ).all()
    
    recent_created = sum(job.items_created for job in recent_jobs)
    recent_updated = sum(job.items_updated for job in recent_jobs)
    
    return {
        "total_feed_items": total_items,
        "total_ingestion_jobs": total_jobs,
        "active_data_sources": active_sources,
        "recent_items_created": recent_created,
        "recent_items_updated": recent_updated,
        "recent_jobs_count": len(recent_jobs)
    }

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get Celery task status"""
    try:
        task = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": task.status,
            "result": task.result if task.ready() else None,
            "info": task.info if hasattr(task, 'info') else None
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {str(e)}")

@app.get("/debug/perplexity-model")
async def debug_perplexity_model(db: SessionLocal = Depends(get_db)):
    """Debug endpoint to check and fix Perplexity model name"""
    try:
        # Find the Perplexity data source
        perplexity_source = db.query(DataSource).filter(
            DataSource.name == "perplexity"
        ).first()
        
        if not perplexity_source:
            return {"error": "Perplexity data source not found"}
        
        current_config = perplexity_source.config or {}
        current_model = current_config.get("model", "not set")
        
        # Check if model needs to be updated
        if current_model != "sonar":
            # Update the model name
            if perplexity_source.config:
                perplexity_source.config["model"] = "sonar"
            else:
                perplexity_source.config = {"model": "sonar"}
            
            db.commit()
            
            return {
                "message": "Perplexity model name updated",
                "old_model": current_model,
                "new_model": "sonar",
                "config": perplexity_source.config
            }
        else:
            return {
                "message": "Perplexity model name is already correct",
                "current_model": current_model,
                "config": perplexity_source.config
            }
            
    except Exception as e:
        return {"error": f"Failed to check/fix Perplexity model: {str(e)}"}

@app.get("/debug/test-perplexity-api")
async def debug_test_perplexity_api():
    """Debug endpoint to test Perplexity API directly"""
    try:
        from runners.perplexity_runner import PerplexityRunner
        
        runner = PerplexityRunner()
        
        # Test a simple query
        result = runner.query_perplexity("What are the top technology news stories today?")
        
        if result:
            return {
                "message": "Perplexity API test successful",
                "has_result": True,
                "result_keys": list(result.keys()) if result else None
            }
        else:
            return {
                "message": "Perplexity API test failed",
                "has_result": False
            }
            
    except Exception as e:
        return {"error": f"Failed to test Perplexity API: {str(e)}"}

@app.get("/debug/user-feed/{user_id}")
async def debug_user_feed(user_id: int, db: SessionLocal = Depends(get_db)):
    """Debug endpoint: show user categories and feed items for a user (including AI filtering results)"""
    # Get user categories
    user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    
    # Get category names and short summaries for this user
    category_names_and_summaries = []
    for cat in user_categories:
        category_names_and_summaries.append(cat.category_name)
        if cat.short_summary:
            category_names_and_summaries.append(cat.short_summary)
    
    # Get feed items for those categories (include both category_name and short_summary)
    feed_items = []
    if category_names_and_summaries:
        feed_items = db.query(FeedItem).filter(FeedItem.category.in_(category_names_and_summaries)).all()
    
    # Separate relevant and irrelevant items
    relevant_items = [item for item in feed_items if item.is_relevant]
    irrelevant_items = [item for item in feed_items if not item.is_relevant]
    
    return {
        "user_id": user_id,
        "categories": [cat.category_name for cat in user_categories],
        "feed_items": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "source": item.source,
                "published_at": to_utc_z(item.published_at) if item.published_at else None,
                "is_relevant": item.is_relevant,
                "relevance_reason": item.relevance_reason
            }
            for item in feed_items
        ],
        "summary": {
            "total_items": len(feed_items),
            "relevant_items": len(relevant_items),
            "irrelevant_items": len(irrelevant_items),
            "relevance_rate": round(len(relevant_items) / len(feed_items) * 100, 1) if feed_items else 0
        }
    }

@app.get("/debug/user-feed-all/{user_id}")
async def debug_user_feed_all(user_id: int, db: SessionLocal = Depends(get_db)):
    """Debug endpoint: show ALL feed items for a user (relevant and irrelevant) - NO AUTH REQUIRED"""
    # Get user categories
    user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    
    # Get category names and short summaries for this user
    category_names_and_summaries = []
    for cat in user_categories:
        category_names_and_summaries.append(cat.category_name)
        if cat.short_summary:
            category_names_and_summaries.append(cat.short_summary)
    
    # Get ALL feed items for those categories (include both category_name and short_summary)
    feed_items = []
    if category_names_and_summaries:
        feed_items = db.query(FeedItem).filter(FeedItem.category.in_(category_names_and_summaries)).order_by(FeedItem.created_at.desc()).all()
    
    # Separate relevant and irrelevant items
    relevant_items = [item for item in feed_items if item.is_relevant]
    irrelevant_items = [item for item in feed_items if not item.is_relevant]
    
    return {
        "user_id": user_id,
        "categories": [cat.category_name for cat in user_categories],
        "feed_items": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "source": item.source,
                "published_at": to_utc_z(item.published_at) if item.published_at else None,
                "created_at": to_utc_z(item.created_at) if item.created_at else None,
                "is_relevant": item.is_relevant,
                "relevance_reason": item.relevance_reason,
                "url": item.url,
                "summary": item.summary
            }
            for item in feed_items
        ],
        "summary": {
            "total_items": len(feed_items),
            "relevant_items": len(relevant_items),
            "irrelevant_items": len(irrelevant_items),
            "relevance_rate": round(len(relevant_items) / len(feed_items) * 100, 1) if feed_items else 0
        },
        "note": "This endpoint shows ALL feed items (relevant and irrelevant) for debugging AI filtering decisions"
    }

@app.get("/debug/reddit-feed")
async def debug_reddit_feed(
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = 20,
    db: SessionLocal = Depends(get_db)
):
    """Debug endpoint: show Reddit feed items with filtering options"""
    query = db.query(FeedItem).filter(FeedItem.source.like('%Reddit%'))
    
    # Filter by user if specified
    if user_id:
        user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
        category_names = [cat.category_name for cat in user_categories]
        if category_names:
            query = query.filter(FeedItem.category.in_(category_names))
    
    # Filter by category if specified
    if category:
        query = query.filter(FeedItem.category == category)
    
    # Get recent items
    reddit_items = query.order_by(FeedItem.created_at.desc()).limit(limit).all()
    
    return {
        "total_reddit_items": len(reddit_items),
        "filters_applied": {
            "user_id": user_id,
            "category": category,
            "limit": limit
        },
        "reddit_items": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "source": item.source,
                "url": item.url,
                "created_at": to_utc_z(item.created_at) if item.created_at else None,
                "published_at": to_utc_z(item.published_at) if item.published_at else None
            }
            for item in reddit_items
        ]
    }

# Feed data deletion APIs
@app.delete("/feed-items/delete/user/{user_id}")
async def delete_feed_data_for_user(
    user_id: int,
    confirm: bool = Query(..., description="Must be true to confirm deletion"),
    db: SessionLocal = Depends(get_db)
):
    """Delete all feed data for a specific user"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    try:
        # Get user's categories
        user_categories = db.query(UserCategory).filter(
            UserCategory.user_id == user_id,
            UserCategory.is_active == True
        ).all()
        
        category_names = [cat.category_name for cat in user_categories]
        
        # Delete feed items for user's categories
        deleted_count = 0
        if category_names:
            deleted_count = db.query(FeedItem).filter(
                FeedItem.category.in_(category_names)
            ).delete()
        
        # Delete user's categories
        categories_deleted = db.query(UserCategory).filter(
            UserCategory.user_id == user_id
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Successfully deleted feed data for user {user_id}",
            "feed_items_deleted": deleted_count,
            "categories_deleted": categories_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting feed data: {str(e)}")

@app.delete("/feed-items/delete/all")
async def delete_all_feed_data(
    confirm: bool = Query(..., description="Must be true to confirm deletion"),
    db: SessionLocal = Depends(get_db)
):
    """Delete all feed data for all users"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    try:
        # Delete all feed items
        feed_items_deleted = db.query(FeedItem).delete()
        
        # Delete all user categories
        categories_deleted = db.query(UserCategory).delete()
        
        db.commit()
        
        return {
            "message": "Successfully deleted all feed data",
            "feed_items_deleted": feed_items_deleted,
            "categories_deleted": categories_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting all feed data: {str(e)}")

@app.delete("/feed-items/delete/category/{category_name}")
async def delete_feed_data_by_category(
    category_name: str,
    confirm: bool = Query(..., description="Must be true to confirm deletion"),
    db: SessionLocal = Depends(get_db)
):
    """Delete all feed data for a specific category"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    try:
        # Delete feed items for the category
        feed_items_deleted = db.query(FeedItem).filter(
            FeedItem.category == category_name
        ).delete()
        
        # Delete user categories with this name
        categories_deleted = db.query(UserCategory).filter(
            UserCategory.category_name == category_name
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Successfully deleted feed data for category '{category_name}'",
            "feed_items_deleted": feed_items_deleted,
            "categories_deleted": categories_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting feed data: {str(e)}")

@app.get("/category-ingestion-history")
async def get_category_ingestion_history(
    category: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 50,
    db: SessionLocal = Depends(get_db)
):
    """Get category-specific ingestion history by analyzing feed items"""
    
    # Get all categories that have feed items
    categories_with_items = db.query(FeedItem.category).distinct().all()
    categories_with_items = [cat[0] for cat in categories_with_items if cat[0]]
    
    # Filter by specific category if provided
    if category:
        categories_with_items = [category] if category in categories_with_items else []
    
    # Filter by user categories if user_id provided
    if user_id:
        user_categories = db.query(UserCategory).filter(
            UserCategory.user_id == user_id,
            UserCategory.is_active == True
        ).all()
        user_category_names = [cat.category_name for cat in user_categories]
        categories_with_items = [cat for cat in categories_with_items if cat in user_category_names]
    
    history = []
    
    for cat_name in categories_with_items:
        # Get the most recent items for this category
        recent_items = db.query(FeedItem).filter(
            FeedItem.category == cat_name
        ).order_by(FeedItem.created_at.desc()).limit(limit).all()
        
        if recent_items:
            # Group items by creation time (within 5 minutes = same ingestion job)
            from collections import defaultdict
            time_groups = defaultdict(list)
            
            for item in recent_items:
                # Round to nearest 5 minutes to group items from same job
                rounded_time = item.created_at.replace(second=0, microsecond=0)
                rounded_time = rounded_time.replace(minute=(rounded_time.minute // 5) * 5)
                time_groups[rounded_time].append(item)
            
            # Create history entries for each time group
            for job_time, items in time_groups.items():
                history.append({
                    "category": cat_name,
                    "job_timestamp": to_utc_z(job_time),
                    "items_created": len(items),
                    "latest_item_id": max(item.id for item in items),
                    "earliest_item_id": min(item.id for item in items),
                    "sample_summaries": [item.summary[:100] + "..." if item.summary and len(item.summary) > 100 else item.summary for item in items[:3]]
                })
    
    # Sort by job timestamp (most recent first)
    history.sort(key=lambda x: x["job_timestamp"], reverse=True)
    
    return {
        "total_categories_with_items": len(set(item["category"] for item in history)),
        "total_ingestion_jobs": len(history),
        "history": history[:limit]
    }

@app.get("/category-status/{user_id}")
async def get_category_status(user_id: int, db: SessionLocal = Depends(get_db)):
    """Get status of all categories for a user (with/without feed items)"""
    
    # Get user's categories
    user_categories = db.query(UserCategory).filter(
        UserCategory.user_id == user_id,
        UserCategory.is_active == True
    ).all()
    
    category_status = []
    
    for category in user_categories:
        # Check if this category has feed items
        feed_items = db.query(FeedItem).filter(
            FeedItem.category == category.category_name
        ).order_by(FeedItem.created_at.desc()).limit(1).all()
        
        latest_item = feed_items[0] if feed_items else None
        
        category_status.append({
            "category_id": category.id,
            "category_name": category.category_name,
            "has_feed_items": len(feed_items) > 0,
            "latest_item_created": to_utc_z(latest_item.created_at) if latest_item else None,
            "latest_item_id": latest_item.id if latest_item else None,
            "category_created": to_utc_z(category.created_at),
            "days_since_category_created": (datetime.utcnow() - category.created_at).days,
            "days_since_last_item": (datetime.utcnow() - latest_item.created_at).days if latest_item else None,
            "minutes_since_last_item": int((datetime.utcnow() - latest_item.created_at).total_seconds() / 60) if latest_item else None
        })
    
    return {
        "user_id": user_id,
        "total_categories": len(category_status),
        "categories_with_items": len([c for c in category_status if c["has_feed_items"]]),
        "categories_without_items": len([c for c in category_status if not c["has_feed_items"]]),
        "category_status": category_status
    }

@app.post("/perplexity/derivatives")
async def perplexity_derivatives(request: Request):
    data = await request.json()
    phrase = data.get("text")
    if not phrase:
        return {"error": "Missing text"}
    # Build the explicit prompt with JSON key details
    prompt = (
        f'Consider the phrase "{phrase}". For this phrase, please respond ONLY in JSON to the following questions: '
        '1. What is an up to 4 word summary of this phrase? The JSON key for this should be "summary" and the value should be a string. '
        '2. What are the most popular subreddits that discuss the topic in this phrase? The JSON key for this should be "reddit" and the value should be a list of subreddit names as strings. '
        '3. What are the most popular twitter handles and hashtags to learn about the topic in the phrase on twitter? The JSON key for this should be "twitter" and the value should be a list of strings, each string being either a handle (starting with @) or a hashtag (starting with #).'
        ' Respond ONLY with a single JSON object with these three keys: "summary", "reddit", and "twitter".'
    )
    perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
    if not perplexity_api_key:
        return {"error": "PERPLEXITY_API_KEY not set in environment"}
    headers = {
        "Authorization": f"Bearer {perplexity_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that responds ONLY in JSON as instructed."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 256,
        "temperature": 0.5
    }
    perplexity_url = "https://api.perplexity.ai/chat/completions"
    try:
        resp = requests.post(perplexity_url, headers=headers, json=payload, timeout=20)
        print(f"[DEBUG] Perplexity API status: {resp.status_code}")
        print(f"[DEBUG] Perplexity API response: {resp.text}")
        if not resp.ok:
            return {"error": f"Perplexity API error: {resp.status_code}", "raw": resp.text}
        result = resp.json()
        # Extract the content from the response
        content = None
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
        if not content:
            return {"error": "No content in Perplexity response", "raw": result}
        # Try to parse the content as JSON
        try:
            # Clean up markdown code block if present
            cleaned = content.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned.replace('```json', '').replace('```', '').strip()
            elif cleaned.startswith('```'):
                cleaned = cleaned.replace('```', '').strip()
            # Remove leading/trailing quotes
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            cleaned = cleaned.replace('\\"', '"')
            parsed = json.loads(cleaned)
        except Exception as e:
            return {"error": f"Failed to parse JSON from Perplexity response: {e}", "raw": content}
        # Validate keys
        if not all(k in parsed for k in ("summary", "reddit", "twitter")):
            return {"error": "Missing one or more required keys in response", "raw": parsed}
        # Validate types
        if not isinstance(parsed["summary"], str):
            return {"error": '"summary" must be a string', "raw": parsed}
        if not isinstance(parsed["reddit"], list) or not all(isinstance(x, str) for x in parsed["reddit"]):
            return {"error": '"reddit" must be a list of strings', "raw": parsed}
        if not isinstance(parsed["twitter"], list) or not all(isinstance(x, str) for x in parsed["twitter"]):
            return {"error": '"twitter" must be a list of strings', "raw": parsed}
        return parsed
    except Exception as e:
        print(f"[ERROR] Exception calling Perplexity: {e}")
        return {"error": f"Exception calling Perplexity: {e}"}

app.include_router(perplexity_debug_router)
app.include_router(reddit_debug_router)
app.include_router(newsapi_debug_router)

@app.get("/debug/cleanup-status")
async def get_cleanup_status():
    """Debug endpoint to check cleanup task status and configuration"""
    return {
        "cleanup_configuration": {
            "scheduled_task": "cleanup-old-feed-items",
            "frequency": "Every 3 hours",
            "retention_policy": "24 hours",
            "task_name": "runners.cleanup_runner.cleanup_old_feed_items"
        },
        "cleanup_features": {
            "automated_cleanup": True,
            "source_based_cleanup": True,
            "category_based_cleanup": True,
            "user_based_cleanup": True
        },
        "cleanup_sources": [
            "Perplexity AI",
            "NewsAPI",
            "Reddit",
            "Social Media"
        ],
        "note": "Cleanup runs automatically every 3 hours and before each source ingestion"
    }

@app.get("/debug/cleanup-stats")
async def get_cleanup_stats(db: SessionLocal = Depends(get_db)):
    """Debug endpoint to show actual cleanup statistics from the database"""
    try:
        from datetime import datetime, timedelta
        
        # Get current time
        now = datetime.utcnow()
        
        # Calculate time thresholds
        cutoff_24h = now - timedelta(hours=24)
        cutoff_48h = now - timedelta(hours=48)
        cutoff_7d = now - timedelta(days=7)
        
        # Count items by age
        items_24h_old = db.query(FeedItem).filter(FeedItem.created_at < cutoff_24h).count()
        items_48h_old = db.query(FeedItem).filter(FeedItem.created_at < cutoff_48h).count()
        items_7d_old = db.query(FeedItem).filter(FeedItem.created_at < cutoff_7d).count()
        total_items = db.query(FeedItem).count()
        
        # Count items by source
        source_counts = {}
        sources = db.query(FeedItem.source).distinct().all()
        for source in sources:
            if source[0]:
                source_counts[source[0]] = db.query(FeedItem).filter(FeedItem.source == source[0]).count()
        
        # Count items by relevance
        relevant_items = db.query(FeedItem).filter(FeedItem.is_relevant == True).count()
        irrelevant_items = db.query(FeedItem).filter(FeedItem.is_relevant == False).count()
        
        return {
            "current_time": now.isoformat(),
            "item_counts": {
                "total_items": total_items,
                "items_older_than_24h": items_24h_old,
                "items_older_than_48h": items_48h_old,
                "items_older_than_7d": items_7d_old
            },
            "relevance_counts": {
                "relevant_items": relevant_items,
                "irrelevant_items": irrelevant_items,
                "relevance_rate": round(relevant_items / total_items * 100, 1) if total_items > 0 else 0
            },
            "source_distribution": source_counts,
            "cleanup_recommendations": {
                "should_cleanup_24h": items_24h_old > 0,
                "should_cleanup_48h": items_48h_old > 0,
                "should_cleanup_7d": items_7d_old > 0
            }
        }
        
    except Exception as e:
        print(f"[ERROR] Cleanup stats error: {e}")
        return {"error": f"Failed to get cleanup stats: {str(e)}"}

@app.get("/debug/ai-summary-test/{user_id}")
async def debug_ai_summary_test(
    user_id: int,
    max_words: int = 300,
    wait_for_completion: bool = True,
    timeout_seconds: int = 60,
    db: SessionLocal = Depends(get_db)
):
    """Debug endpoint: Test AI summary generation for a specific user (synchronous - Celery coming later)"""
    try:
        print(f"[DEBUG] Starting AI summary test for user {user_id}")
        
        # Check if user exists and has categories
        user_categories = db.query(UserCategory).filter(
            UserCategory.user_id == user_id,
            UserCategory.is_active == True
        ).all()
        
        if not user_categories:
            return {
                "user_id": user_id,
                "status": "error",
                "message": f"No active categories found for user {user_id}",
                "can_generate_summary": False
            }
        
        # Check if user has feed items
        category_names = [cat.category_name for cat in user_categories]
        feed_items = db.query(FeedItem).filter(
            FeedItem.category.in_(category_names),
            FeedItem.is_relevant == True
        ).all()
        
        if not feed_items:
            return {
                "user_id": user_id,
                "status": "error",
                "message": f"No relevant feed items found for user {user_id}",
                "can_generate_summary": False
            }
        
        # For now, generate summary synchronously
        # This will be replaced with Celery integration later
        print(f"[DEBUG] Generating AI summary synchronously for user {user_id}")
        
        result_data = {
            "user_id": user_id,
            "task_status": "completed_synchronously",
            "max_words": max_words,
            "user_categories": [cat.category_name for cat in user_categories],
            "total_feed_items": len(feed_items),
            "categories_with_items": len(set(item.category for item in feed_items)),
            "submitted_at": datetime.utcnow().isoformat(),
            "note": "Currently running synchronously - Celery integration coming later"
        }
        
        if not wait_for_completion:
            return {
                **result_data,
                "message": f"AI summary test completed synchronously for user {user_id}."
            }
        
        # Generate the summary directly in this endpoint
        try:
            # Group feed items by category
            category_feed_data = {}
            for category in user_categories:
                category_items = [item for item in feed_items if item.category == category.category_name]
                if category_items:
                    category_feed_data[category.category_name] = [
                        {
                            "title": item.title,
                            "summary": item.summary,
                            "source": item.source,
                            "published_at": to_utc_z(item.published_at) if item.published_at else None,
                            "url": item.url
                        }
                        for item in category_items[:20]  # Limit to 20 items per category
                    ]
            
            # Create the JSON structure for Perplexity
            feed_summary_data = {
                "user_categories": list(category_feed_data.keys()),
                "feed_items_by_category": category_feed_data
            }
            
            # Generate the prompt for Perplexity
            prompt = f"""Given this JSON structure that is organized by the topic category and news items on that category, generate a summarization for the user to read as a briefing. The summary should be up to {max_words} words long.

JSON Structure:
{json.dumps(feed_summary_data, indent=2)}

Please provide a comprehensive yet concise summary that:
1. Highlights the most important developments across all categories
2. Identifies any emerging trends or patterns
3. Provides context for why these items matter
4. Is written in a professional briefing format
5. Stays within the {max_words} word limit

Respond with a well-structured summary that flows naturally between topics."""
            
            # Call Perplexity API
            perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
            if not perplexity_api_key:
                return {
                    **result_data,
                    "task_status": "failed",
                    "completion_time": datetime.utcnow().isoformat(),
                    "error": "PERPLEXITY_API_KEY not configured"
                }
            
            headers = {
                "Authorization": f"Bearer {perplexity_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are an expert news analyst and briefing writer. Your task is to create concise, informative summaries of news items organized by category. Focus on clarity, relevance, and actionable insights."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.3
            }
            
            perplexity_url = "https://api.perplexity.ai/chat/completions"
            response = requests.post(perplexity_url, headers=headers, json=payload, timeout=30)
            
            if not response.ok:
                return {
                    **result_data,
                    "task_status": "failed",
                    "completion_time": datetime.utcnow().isoformat(),
                    "error": f"Perplexity API error: {response.status_code} - {response.text}"
                }
            
            result = response.json()
            if "choices" not in result or not result["choices"]:
                return {
                    **result_data,
                    "task_status": "failed",
                    "completion_time": datetime.utcnow().isoformat(),
                    "error": "Invalid response from Perplexity API"
                }
            
            summary_content = result["choices"][0]["message"]["content"]
            
            # Count actual words in the summary
            actual_word_count = len(summary_content.split())
            
            summary_result = {
                "user_id": user_id,
                "summary": summary_content,
                "word_count": actual_word_count,
                "max_words_requested": max_words,
                "categories_covered": list(category_feed_data.keys()),
                "total_feed_items_analyzed": len(feed_items),
                "generated_at": datetime.utcnow().isoformat(),
                "source": "Perplexity AI"
            }
            
            return {
                **result_data,
                "task_status": "completed",
                "completion_time": datetime.utcnow().isoformat(),
                "result": summary_result,
                "summary_preview": summary_result.get("summary", "")[:200] + "..." if summary_result.get("summary") and len(summary_result.get("summary", "")) > 200 else summary_result.get("summary", "")
            }
            
        except Exception as e:
            return {
                **result_data,
                "task_status": "failed",
                "completion_time": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        
    except Exception as e:
        print(f"[ERROR] Debug AI summary test failed for user {user_id}: {e}")
        return {
            "user_id": user_id,
            "status": "error",
            "message": f"Debug test failed: {str(e)}",
            "error_type": type(e).__name__
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 