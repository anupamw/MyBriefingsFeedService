from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
import json

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
from shared.database.connection import SessionLocal, init_database
from shared.models.database_models import DataSource, FeedItem, IngestionJob, UserCategory, UserDB
from celery_app import celery_app
from runners.perplexity_runner import PerplexityRunner, router as perplexity_debug_router
from runners.reddit_runner import RedditRunner
from runners.social_runner import SocialRunner

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
    """Debug endpoint: show user categories and feed items for a user"""
    # Get user categories
    user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    category_names = [cat.category_name for cat in user_categories]
    # Get feed items for those categories
    feed_items = []
    if category_names:
        feed_items = db.query(FeedItem).filter(FeedItem.category.in_(category_names)).all()
    return {
        "user_id": user_id,
        "categories": category_names,
        "feed_items": [
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "published_at": to_utc_z(item.published_at) if item.published_at else None
            }
            for item in feed_items
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

app.include_router(perplexity_debug_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 