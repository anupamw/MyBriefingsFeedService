import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/feed.db")

# Create engine with appropriate configuration
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration for development
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )
else:
    # PostgreSQL configuration for production
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Get database session with proper cleanup"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database tables"""
    from shared.models.database_models import Base
    
    # Import all models to ensure they're registered
    from shared.models.database_models import (
        DataSource, FeedItem, IngestionJob, UserCategory, 
        UserDB, ContentCache
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Run database migration to update existing tables
    migrate_database_schema()
    
    # Initialize default data sources
    init_default_data_sources(DataSource)

def migrate_database_schema():
    """Migrate database schema to support longer titles and URLs"""
    try:
        # Check if we're using PostgreSQL
        if DATABASE_URL.startswith("postgresql"):
            print("Migrating PostgreSQL database schema...")
            
            with engine.connect() as conn:
                # Update title column to VARCHAR(500) if it's currently smaller
                conn.execute(text("""
                    ALTER TABLE feed_items 
                    ALTER COLUMN title TYPE VARCHAR(500)
                """))
                
                # Update url column to VARCHAR(1000) if it's currently smaller
                conn.execute(text("""
                    ALTER TABLE feed_items 
                    ALTER COLUMN url TYPE VARCHAR(1000)
                """))
                
                conn.commit()
                print("Successfully updated feed_items table schema")
                
        else:
            print("SQLite database detected - no migration needed (SQLite is flexible with field lengths)")
            
    except Exception as e:
        print(f"Migration error (this may be expected if columns already have correct types): {e}")
        # Check if columns already have the right type
        if "already exists" in str(e) or "does not exist" in str(e) or "type" in str(e).lower():
            print("Migration may have already been applied or is not needed")
        else:
            print(f"Unexpected migration error: {e}")

def init_default_data_sources(DataSource):
    """Initialize default data sources"""
    db = SessionLocal()
    try:
        # Check if data sources already exist
        existing_sources = db.query(DataSource).count()
        if existing_sources > 0:
            return
        
        # Create default data sources
        default_sources = [
            {
                "name": "perplexity",
                "display_name": "Perplexity AI",
                "base_url": "https://api.perplexity.ai",
                "rate_limit_per_minute": 10,
                "config": {
                    "model": "sonar",
                    "max_tokens": 1000
                }
            },
            # Disabled data sources - uncomment to enable
            {
                "name": "reddit",
                "display_name": "Reddit",
                "base_url": "https://www.reddit.com",
                "rate_limit_per_minute": 60,
                "config": {
                    "user_agent": "MyBriefingsFeedService/1.0",
                    "subreddits": ["news", "technology", "science", "worldnews"]
                }
            },
            # {
            #     "name": "newsapi",
            #     "display_name": "News API",
            #     "base_url": "https://newsapi.org/v2",
            #     "rate_limit_per_minute": 100,
            #     "config": {
            #         "default_language": "en",
            #         "default_country": "us"
            #     }
            # }
        ]
        
        for source_data in default_sources:
            source = DataSource(**source_data)
            db.add(source)
        
        db.commit()
        print("Default data sources initialized")
        
    except Exception as e:
        print(f"Error initializing default data sources: {e}")
        db.rollback()
    finally:
        db.close()

def get_database_url():
    """Get database URL for external tools"""
    return DATABASE_URL 