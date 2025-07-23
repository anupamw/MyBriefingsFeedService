#!/usr/bin/env python3
"""
Database migration script to update feed_items table schema
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/feed.db")

def migrate_database():
    """Migrate database schema to support longer titles and URLs"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # Check if we're using PostgreSQL
            if DATABASE_URL.startswith("postgresql"):
                print("Migrating PostgreSQL database...")
                
                # Update title column to VARCHAR(500)
                conn.execute(text("""
                    ALTER TABLE feed_items 
                    ALTER COLUMN title TYPE VARCHAR(500)
                """))
                
                # Update url column to VARCHAR(1000)
                conn.execute(text("""
                    ALTER TABLE feed_items 
                    ALTER COLUMN url TYPE VARCHAR(1000)
                """))
                
                print("Successfully updated feed_items table schema")
                
            else:
                print("SQLite database detected - no migration needed (SQLite is flexible with field lengths)")
                
        except Exception as e:
            print(f"Migration error: {e}")
            # Check if columns already have the right type
            if "already exists" in str(e) or "does not exist" in str(e):
                print("Migration may have already been applied or is not needed")
            else:
                raise e
        
        conn.commit()

if __name__ == "__main__":
    migrate_database() 