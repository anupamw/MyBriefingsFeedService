#!/usr/bin/env python3
"""
Migration script to add AI filtering fields to feed_items table
"""

import os
import sys
from sqlalchemy import create_engine, Column, Boolean, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared.database.connection import DATABASE_URL

def migrate_add_ai_filtering():
    """Add AI filtering fields to feed_items table"""
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print("🔄 Starting migration: Adding AI filtering fields to feed_items table...")
        
        # Check if columns already exist
        inspector = db.bind.dialect.inspector(db.bind)
        existing_columns = [col['name'] for col in inspector.get_columns('feed_items')]
        
        columns_to_add = []
        
        if 'is_relevant' not in existing_columns:
            columns_to_add.append("ADD COLUMN is_relevant BOOLEAN DEFAULT TRUE")
            print("  - Adding is_relevant column")
        
        if 'relevance_reason' not in existing_columns:
            columns_to_add.append("ADD COLUMN relevance_reason TEXT")
            print("  - Adding relevance_reason column")
        
        if columns_to_add:
            # Execute ALTER TABLE statements
            for column_sql in columns_to_add:
                sql = f"ALTER TABLE feed_items {column_sql}"
                print(f"  - Executing: {sql}")
                db.execute(sql)
            
            db.commit()
            print("✅ Migration completed successfully!")
        else:
            print("✅ All AI filtering fields already exist!")
        
        # Verify the migration
        inspector = db.bind.dialect.inspector(db.bind)
        final_columns = [col['name'] for col in inspector.get_columns('feed_items')]
        
        print("\n📊 Final table structure:")
        for col in inspector.get_columns('feed_items'):
            print(f"  - {col['name']}: {col['type']}")
        
        # Check if all required columns exist
        required_columns = ['is_relevant', 'relevance_reason']
        missing_columns = [col for col in required_columns if col not in final_columns]
        
        if missing_columns:
            print(f"❌ Missing columns: {missing_columns}")
            return False
        else:
            print("✅ All required columns are present!")
            return True
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = migrate_add_ai_filtering()
    sys.exit(0 if success else 1) 