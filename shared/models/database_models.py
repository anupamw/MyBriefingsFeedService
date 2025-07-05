from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class DataSource(Base):
    """Track different data sources and their configurations"""
    __tablename__ = "data_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # e.g., "perplexity", "reddit", "newsapi"
    display_name = Column(String(200), nullable=False)  # e.g., "Perplexity AI", "Reddit", "News API"
    api_key = Column(String(500))  # Encrypted API key
    base_url = Column(String(500))
    rate_limit_per_minute = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Configuration for this source
    config = Column(JSON)  # Store source-specific configuration
    
    # Relationships
    feed_items = relationship("FeedItem", back_populates="data_source")

class FeedItem(Base):
    """Enhanced feed items with source tracking and metadata"""
    __tablename__ = "feed_items"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    content = Column(Text)
    url = Column(String(1000))
    source = Column(String(100))  # Original source (e.g., "BBC", "TechCrunch")
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Data source tracking
    data_source_id = Column(Integer, ForeignKey("data_sources.id"))
    data_source = relationship("DataSource", back_populates="feed_items")
    
    # Content metadata
    language = Column(String(10), default="en")
    sentiment_score = Column(Float)  # -1 to 1
    category = Column(String(100))  # Auto-detected or assigned category
    tags = Column(JSON)  # Array of tags
    
    # Engagement metrics (if available)
    engagement_score = Column(Float)
    view_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    
    # Processing metadata
    is_processed = Column(Boolean, default=False)
    processing_priority = Column(Integer, default=1)  # 1=high, 5=low
    last_processed = Column(DateTime)
    
    # Raw data from source
    raw_data = Column(JSON)  # Store original response from API
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_feed_items_published_at', 'published_at'),
        Index('idx_feed_items_source', 'source'),
        Index('idx_feed_items_category', 'category'),
        Index('idx_feed_items_processed', 'is_processed'),
    )

class IngestionJob(Base):
    """Track ingestion jobs and their status"""
    __tablename__ = "ingestion_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(50), nullable=False)  # "perplexity", "reddit", "newsapi"
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Job parameters
    parameters = Column(JSON)  # Query parameters, filters, etc.
    
    # Results
    items_processed = Column(Integer, default=0)
    items_created = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    data_source_id = Column(Integer, ForeignKey("data_sources.id"))

class UserCategory(Base):
    """User categories (moved from main.py for shared access)"""
    __tablename__ = "user_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    category_name = Column(String(140), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Category preferences
    keywords = Column(JSON)  # Array of keywords for this category
    sources = Column(JSON)  # Preferred sources for this category
    is_active = Column(Boolean, default=True)

class UserDB(Base):
    """User model (moved from main.py for shared access)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ContentCache(Base):
    """Cache for API responses to avoid rate limiting"""
    __tablename__ = "content_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(500), unique=True, nullable=False)  # Hash of request parameters
    data_source = Column(String(100), nullable=False)
    response_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Index for cache cleanup
    __table_args__ = (
        Index('idx_content_cache_expires', 'expires_at'),
    ) 