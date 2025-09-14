-- Database initialization script for local development
-- This script runs when PostgreSQL container starts for the first time

-- Create database if it doesn't exist (usually already created by POSTGRES_DB)
-- CREATE DATABASE briefings_feed;

-- Connect to the database
\c briefings_feed;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The actual table creation will be handled by SQLAlchemy models
-- This file can be used for any additional setup needed for local development

