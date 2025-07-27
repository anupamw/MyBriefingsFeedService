#!/usr/bin/env python3
"""
Database migration script to add image_url column to feed_items table
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_add_image_url():
    """Add image_url column to feed_items table"""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL", "postgresql://fastapi:password@localhost:5432/briefings_feed")
    
    print(f"🔧 Starting migration to add image_url column...")
    print(f"📊 Database: {database_url}")
    
    try:
        # Create database engine
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if image_url column already exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'feed_items' 
                AND column_name = 'image_url'
            """))
            
            if result.fetchone():
                print("✅ image_url column already exists in feed_items table")
                return
            
            # Add image_url column
            print("🔧 Adding image_url column to feed_items table...")
            conn.execute(text("""
                ALTER TABLE feed_items 
                ADD COLUMN image_url VARCHAR(1000)
            """))
            
            # Commit the transaction
            conn.commit()
            
            print("✅ Successfully added image_url column to feed_items table")
            
            # Verify the column was added
            result = conn.execute(text("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = 'feed_items' 
                AND column_name = 'image_url'
            """))
            
            column_info = result.fetchone()
            if column_info:
                print(f"✅ Verified: image_url column added with type {column_info[1]} (max length: {column_info[2]})")
            else:
                print("❌ Warning: Could not verify image_url column was added")
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_add_image_url() 