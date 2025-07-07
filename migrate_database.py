#!/usr/bin/env python3
"""
Database migration script to add missing columns for ingestion service
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fastapi:password@localhost:5432/briefings_feed")
engine = create_engine(DATABASE_URL)

def migrate_database():
    """Add missing columns to existing tables"""
    print("🔧 Starting database migration...")
    
    with engine.connect() as conn:
        # Check if feed_items table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'feed_items'
            );
        """))
        feed_items_exists = result.scalar()
        
        if not feed_items_exists:
            print("❌ feed_items table doesn't exist. Creating it...")
            # Create the feed_items table with all required columns
            conn.execute(text("""
                CREATE TABLE feed_items (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    summary TEXT,
                    content TEXT,
                    url VARCHAR(1000),
                    source VARCHAR(100),
                    published_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_source_id INTEGER,
                    language VARCHAR(10) DEFAULT 'en',
                    sentiment_score FLOAT,
                    category VARCHAR(100),
                    tags JSON,
                    engagement_score FLOAT,
                    view_count INTEGER DEFAULT 0,
                    share_count INTEGER DEFAULT 0,
                    is_processed BOOLEAN DEFAULT FALSE,
                    processing_priority INTEGER DEFAULT 1,
                    last_processed TIMESTAMP,
                    raw_data JSON
                );
            """))
            print("✅ feed_items table created")
        else:
            print("✅ feed_items table exists")
            
            # Check if updated_at column exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'feed_items' 
                    AND column_name = 'updated_at'
                );
            """))
            updated_at_exists = result.scalar()
            
            if not updated_at_exists:
                print("➕ Adding updated_at column to feed_items...")
                conn.execute(text("ALTER TABLE feed_items ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
                print("✅ updated_at column added")
            else:
                print("✅ updated_at column already exists")
        
        # Check if user_categories table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_categories'
            );
        """))
        user_categories_exists = result.scalar()
        
        if not user_categories_exists:
            print("❌ user_categories table doesn't exist. Creating it...")
            # Create the user_categories table with all required columns
            conn.execute(text("""
                CREATE TABLE user_categories (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    category_name VARCHAR(140) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    keywords JSON,
                    sources JSON,
                    is_active BOOLEAN DEFAULT TRUE
                );
            """))
            print("✅ user_categories table created")
        else:
            print("✅ user_categories table exists")
            
            # Check if keywords column exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'user_categories' 
                    AND column_name = 'keywords'
                );
            """))
            keywords_exists = result.scalar()
            
            if not keywords_exists:
                print("➕ Adding keywords column to user_categories...")
                conn.execute(text("ALTER TABLE user_categories ADD COLUMN keywords JSON;"))
                print("✅ keywords column added")
            else:
                print("✅ keywords column already exists")
            
            # Check if sources column exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'user_categories' 
                    AND column_name = 'sources'
                );
            """))
            sources_exists = result.scalar()
            
            if not sources_exists:
                print("➕ Adding sources column to user_categories...")
                conn.execute(text("ALTER TABLE user_categories ADD COLUMN sources JSON;"))
                print("✅ sources column added")
            else:
                print("✅ sources column already exists")
            
            # Check if is_active column exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'user_categories' 
                    AND column_name = 'is_active'
                );
            """))
            is_active_exists = result.scalar()
            
            if not is_active_exists:
                print("➕ Adding is_active column to user_categories...")
                conn.execute(text("ALTER TABLE user_categories ADD COLUMN is_active BOOLEAN DEFAULT TRUE;"))
                print("✅ is_active column added")
            else:
                print("✅ is_active column already exists")
        
        # Check if data_sources table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'data_sources'
            );
        """))
        data_sources_exists = result.scalar()
        
        if not data_sources_exists:
            print("❌ data_sources table doesn't exist. Creating it...")
            # Create the data_sources table
            conn.execute(text("""
                CREATE TABLE data_sources (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    display_name VARCHAR(200) NOT NULL,
                    api_key VARCHAR(500),
                    base_url VARCHAR(500),
                    rate_limit_per_minute INTEGER DEFAULT 60,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    config JSON
                );
            """))
            print("✅ data_sources table created")
            
            # Insert default Perplexity data source
            conn.execute(text("""
                INSERT INTO data_sources (name, display_name, base_url, rate_limit_per_minute, is_active)
                VALUES ('perplexity', 'Perplexity AI', 'https://api.perplexity.ai', 10, true)
                ON CONFLICT (name) DO NOTHING;
            """))
            print("✅ Default Perplexity data source inserted")
        else:
            print("✅ data_sources table exists")
        
        # Check if ingestion_jobs table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'ingestion_jobs'
            );
        """))
        ingestion_jobs_exists = result.scalar()
        
        if not ingestion_jobs_exists:
            print("❌ ingestion_jobs table doesn't exist. Creating it...")
            # Create the ingestion_jobs table
            conn.execute(text("""
                CREATE TABLE ingestion_jobs (
                    id SERIAL PRIMARY KEY,
                    job_type VARCHAR(50) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    parameters JSON,
                    items_processed INTEGER DEFAULT 0,
                    items_created INTEGER DEFAULT 0,
                    items_updated INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_source_id INTEGER
                );
            """))
            print("✅ ingestion_jobs table created")
        else:
            print("✅ ingestion_jobs table exists")
        
        # Commit the changes
        conn.commit()
    
    print("🎉 Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database() 