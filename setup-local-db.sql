-- Setup Local Database Schema
-- This script drops all existing tables and recreates the complete schema

-- Drop all tables in correct order (respecting foreign key constraints)
DROP TABLE IF EXISTS content_cache CASCADE;
DROP TABLE IF EXISTS ingestion_jobs CASCADE;
DROP TABLE IF EXISTS feed_items CASCADE;
DROP TABLE IF EXISTS data_sources CASCADE;
DROP TABLE IF EXISTS user_categories CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_users_id ON users (id);
CREATE INDEX ix_users_username ON users (username);
CREATE INDEX ix_users_email ON users (email);

-- Create data_sources table
CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    api_key VARCHAR(500),
    base_url VARCHAR(500),
    rate_limit_per_minute INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    last_used TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    config JSON
);

CREATE INDEX ix_data_sources_id ON data_sources (id);

-- Create feed_items table
CREATE TABLE feed_items (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    content TEXT,
    url VARCHAR(1000),
    image_url VARCHAR(1000),
    source VARCHAR(100),
    published_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    data_source_id INTEGER REFERENCES data_sources(id),
    language VARCHAR(10) DEFAULT 'en',
    sentiment_score FLOAT,
    category VARCHAR(100),
    tags JSON,
    engagement_score FLOAT,
    view_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    is_processed BOOLEAN DEFAULT FALSE,
    processing_priority INTEGER DEFAULT 1,
    last_processed TIMESTAMP WITHOUT TIME ZONE,
    is_relevant BOOLEAN DEFAULT TRUE,
    relevance_reason TEXT,
    raw_data JSON
);

CREATE INDEX ix_feed_items_id ON feed_items (id);
CREATE INDEX idx_feed_items_published_at ON feed_items (published_at);
CREATE INDEX idx_feed_items_source ON feed_items (source);
CREATE INDEX idx_feed_items_category ON feed_items (category);
CREATE INDEX idx_feed_items_processed ON feed_items (is_processed);
CREATE INDEX idx_feed_items_relevant ON feed_items (is_relevant);

-- Create ingestion_jobs table
CREATE TABLE ingestion_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    error_message TEXT,
    parameters JSON,
    items_processed INTEGER DEFAULT 0,
    items_created INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    data_source_id INTEGER REFERENCES data_sources(id)
);

CREATE INDEX ix_ingestion_jobs_id ON ingestion_jobs (id);

-- Create user_categories table
CREATE TABLE user_categories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    category_name VARCHAR(140) NOT NULL,
    short_summary VARCHAR(50),
    subreddits TEXT,
    twitter TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    keywords JSON,
    sources JSON,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX ix_user_categories_id ON user_categories (id);

-- Create content_cache table
CREATE TABLE content_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(500) UNIQUE NOT NULL,
    data_source VARCHAR(100) NOT NULL,
    response_data JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE INDEX ix_content_cache_id ON content_cache (id);
CREATE INDEX idx_content_cache_expires ON content_cache (expires_at);

-- Insert default data sources
INSERT INTO data_sources (name, display_name, is_active, config) VALUES
('perplexity', 'Perplexity AI', TRUE, '{"model": "llama-3.1-sonar-small-128k-online"}'),
('newsapi', 'News API', TRUE, '{"base_url": "https://newsapi.org/v2"}'),
('reddit', 'Reddit', TRUE, '{"base_url": "https://www.reddit.com"}');

-- Create a default user for testing
INSERT INTO users (username, email, hashed_password) VALUES
('testuser', 'test@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj5J5j5j5j5j');

-- Create some default categories for the test user
INSERT INTO user_categories (user_id, category_name, short_summary, keywords, is_active) VALUES
(1, 'Technology', 'Tech news', '["technology", "AI", "software", "startups"]', TRUE),
(1, 'Finance', 'Financial news', '["finance", "stocks", "crypto", "economy"]', TRUE),
(1, 'Science', 'Science updates', '["science", "research", "discoveries"]', TRUE);

COMMIT;

