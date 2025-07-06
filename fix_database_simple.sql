-- Simple SQL script to fix the database schema
-- Run this on your droplet

-- Add missing updated_at column to feed_items table
ALTER TABLE feed_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Add missing columns to user_categories table
ALTER TABLE user_categories ADD COLUMN IF NOT EXISTS keywords JSON;
ALTER TABLE user_categories ADD COLUMN IF NOT EXISTS sources JSON;
ALTER TABLE user_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Update existing records to have updated_at set to created_at
UPDATE feed_items SET updated_at = created_at WHERE updated_at IS NULL;

-- Show the updated table structure
\d feed_items;
\d user_categories; 