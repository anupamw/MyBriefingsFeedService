-- Migration script to add AI filtering fields to feed_items table
-- Run this with: psql "postgresql://fastapi:password@64.227.134.87:5432/briefings_feed" -f migrate_add_ai_filtering.sql

-- Add the is_relevant column (if it doesn't exist)
ALTER TABLE feed_items ADD COLUMN IF NOT EXISTS is_relevant BOOLEAN DEFAULT TRUE;

-- Add the relevance_reason column (if it doesn't exist)
ALTER TABLE feed_items ADD COLUMN IF NOT EXISTS relevance_reason TEXT;

-- Create an index for better performance (if it doesn't exist)
CREATE INDEX IF NOT EXISTS idx_feed_items_relevant ON feed_items(is_relevant);

-- Verify the migration by showing the table structure
\d feed_items;

-- Show a summary of the migration
SELECT 
    'Migration completed successfully!' as status,
    COUNT(*) as total_feed_items,
    COUNT(CASE WHEN is_relevant = true THEN 1 END) as relevant_items,
    COUNT(CASE WHEN is_relevant = false THEN 1 END) as irrelevant_items
FROM feed_items; 