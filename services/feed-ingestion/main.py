from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
from shared.database.connection import SessionLocal, init_database
from shared.models.database_models import DataSource, FeedItem, IngestionJob, UserCategory, UserDB
from services.feed_ingestion.celery_app import celery_app
from services.feed_ingestion.runners.perplexity_runner import PerplexityRunner
from services.feed_ingestion.runners.reddit_runner import RedditRunner
from services.feed_ingestion.runners.social_runner import SocialRunner

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

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_database()

@app.get("/health")
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
            last_used=source.last_used.isoformat() if source.last_used else None,
            created_at=source.created_at.isoformat(),
            updated_at=source.updated_at.isoformat()
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
        last_used=db_source.last_used.isoformat() if db_source.last_used else None,
        created_at=db_source.created_at.isoformat(),
        updated_at=db_source.updated_at.isoformat()
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
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error_message=job.error_message,
            items_processed=job.items_processed,
            items_created=job.items_created,
            items_updated=job.items_updated,
            created_at=job.created_at.isoformat()
        )
        for job in jobs
    ]

@app.post("/ingest/perplexity")
async def trigger_perplexity_ingestion(
    queries: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None
):
    """Trigger Perplexity ingestion job"""
    try:
        # Submit Celery task
        task = celery_app.send_task(
            "services.feed_ingestion.runners.perplexity_runner.ingest_perplexity",
            args=[queries]
        )
        
        return {
            "message": "Perplexity ingestion job started",
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
            "services.feed_ingestion.runners.reddit_runner.ingest_reddit",
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
            "services.feed_ingestion.runners.social_runner.ingest_social",
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
    db: SessionLocal = Depends(get_db)
):
    """Get feed items with optional filtering"""
    query = db.query(FeedItem)
    
    if category:
        query = query.filter(FeedItem.category == category)
    if source:
        query = query.filter(FeedItem.source == source)
    
    items = query.order_by(FeedItem.published_at.desc()).offset(offset).limit(limit).all()
    
    return [
        FeedItemResponse(
            id=item.id,
            title=item.title,
            summary=item.summary,
            content=item.content,
            url=item.url,
            source=item.source,
            published_at=item.published_at.isoformat() if item.published_at else None,
            created_at=item.created_at.isoformat(),
            category=item.category,
            engagement_score=item.engagement_score,
            tags=item.tags
        )
        for item in items
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 