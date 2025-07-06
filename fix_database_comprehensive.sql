-- Comprehensive database schema fix for ingestion service
-- Add all missing columns that the ingestion service expects

-- Add missing columns to feed_items table
ALTER TABLE feed_items 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS data_source_id INTEGER,
ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en',
ADD COLUMN IF NOT EXISTS sentiment_score DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS category VARCHAR(100),
ADD COLUMN IF NOT EXISTS tags TEXT,
ADD COLUMN IF NOT EXISTS engagement_score DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS share_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS is_processed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS processing_priority INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_processed TIMESTAMP,
ADD COLUMN IF NOT EXISTS raw_data JSONB;

-- Add missing columns to user_categories table
ALTER TABLE user_categories 
ADD COLUMN IF NOT EXISTS keywords TEXT,
ADD COLUMN IF NOT EXISTS sources TEXT,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Create sources table if it doesn't exist
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    url VARCHAR(500),
    description TEXT,
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create data_sources table if it doesn't exist
CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,
    config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create ingestion_logs table if it doesn't exist
CREATE TABLE IF NOT EXISTS ingestion_logs (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(200),
    status VARCHAR(50),
    items_processed INTEGER DEFAULT 0,
    items_added INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_feed_items_published_at ON feed_items(published_at);
CREATE INDEX IF NOT EXISTS idx_feed_items_category ON feed_items(category);
CREATE INDEX IF NOT EXISTS idx_feed_items_is_processed ON feed_items(is_processed);
CREATE INDEX IF NOT EXISTS idx_user_categories_user_id ON user_categories(user_id);
CREATE INDEX IF NOT EXISTS idx_user_categories_is_active ON user_categories(is_active);

-- Update existing records to have default values
UPDATE feed_items SET 
    updated_at = created_at WHERE updated_at IS NULL;

UPDATE user_categories SET 
    is_active = TRUE WHERE is_active IS NULL;

-- Verify the changes
SELECT 'feed_items table columns:' as info;
\d feed_items;

SELECT 'user_categories table columns:' as info;
\d user_categories;

SELECT 'Tables created/updated successfully!' as status; 