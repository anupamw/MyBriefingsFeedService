#!/usr/bin/env python3
"""
Database migration script to add refresh token support
Run this script to add the refresh_tokens table to your existing database
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

def run_migration():
    """Run the database migration to add refresh tokens table"""
    
    # Get database URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fastapi:password@localhost:5432/briefings_feed")
    
    print(f"🔧 Connecting to database: {DATABASE_URL.split('@')[-1]}")  # Hide credentials
    
    try:
        engine = create_engine(DATABASE_URL)
        
        # Create the refresh_tokens table
        migration_sql = """
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            user_agent VARCHAR(500),
            ip_address VARCHAR(45)
        );
        
        -- Create indexes for efficient lookups
        CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
        CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
        CREATE INDEX IF NOT EXISTS idx_refresh_tokens_active ON refresh_tokens(is_active);
        CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
        
        -- Add foreign key constraint (optional, uncomment if you want referential integrity)
        -- ALTER TABLE refresh_tokens ADD CONSTRAINT fk_refresh_tokens_user_id 
        -- FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        """
        
        with engine.connect() as conn:
            # Execute the migration
            conn.execute(text(migration_sql))
            conn.commit()
            
            # Verify the table was created
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'refresh_tokens'
            """))
            
            if result.fetchone():
                print("✅ Successfully created refresh_tokens table")
                
                # Check indexes
                index_result = conn.execute(text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'refresh_tokens'
                """))
                
                indexes = [row[0] for row in index_result.fetchall()]
                print(f"✅ Created {len(indexes)} indexes: {', '.join(indexes)}")
                
            else:
                print("❌ Failed to create refresh_tokens table")
                return False
                
        print("🎉 Migration completed successfully!")
        print("\n📋 Next steps:")
        print("1. Restart your FastAPI application")
        print("2. Test login to verify refresh tokens are working")
        print("3. Check /auth/refresh-tokens/stats endpoint for token management")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def rollback_migration():
    """Rollback the migration (drop refresh_tokens table)"""
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fastapi:password@localhost:5432/briefings_feed")
    
    print(f"⚠️  Rolling back migration...")
    
    try:
        engine = create_engine(DATABASE_URL)
        
        rollback_sql = """
        DROP TABLE IF EXISTS refresh_tokens CASCADE;
        """
        
        with engine.connect() as conn:
            conn.execute(text(rollback_sql))
            conn.commit()
            
        print("✅ Successfully rolled back migration")
        return True
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False

if __name__ == "__main__":
    print("🔐 Refresh Token Migration Script")
    print("=" * 40)
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        run_migration()
