# Feed Ingestion Service

A FastAPI-based service for ingesting and processing feed data from various sources including Perplexity AI, Reddit, RSS feeds, and social media platforms.

## Features

- **Multi-source ingestion**: Perplexity AI, Reddit, RSS feeds, Mastodon, GitHub
- **Background job processing**: Celery with Redis for reliable job execution
- **Scheduled ingestion**: Automatic periodic data collection
- **Content caching**: Redis-based caching to avoid rate limits
- **Comprehensive API**: RESTful endpoints for managing ingestion jobs
- **Database integration**: Shared SQLite/PostgreSQL database with main service

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Celery Worker  │    │  Celery Beat    │
│   (Port 8001)   │    │  (Background)   │    │  (Scheduler)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │      Redis      │
                    │   (Job Queue)   │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   SQLite/PostgreSQL │
                    │   (Shared DB)   │
                    └─────────────────┘
```

## Data Sources

### 1. Perplexity AI
- **Purpose**: AI-generated summaries of current events
- **Rate Limit**: 10 requests/minute
- **Content**: Technology, world events, AI developments, science, business news

### 2. Reddit
- **Purpose**: Trending posts from popular subreddits
- **Rate Limit**: 60 requests/minute
- **Subreddits**: news, technology, science, worldnews, programming, MachineLearning

### 3. Social Media (RSS + Mastodon + GitHub)
- **RSS Feeds**: TechCrunch, Ars Technica, BBC News, Hacker News, The Verge
- **Mastodon**: Public posts from mastodon.social and tech.lgbt
- **GitHub**: Trending repositories

## API Endpoints

### Health Check
```
GET /health
```

### Data Sources
```
GET /data-sources                    # List all data sources
POST /data-sources                   # Create new data source
PUT /data-sources/{id}/toggle        # Toggle source active status
```

### Ingestion Jobs
```
GET /ingestion-jobs                  # List ingestion jobs
POST /ingest/perplexity              # Trigger Perplexity ingestion
POST /ingest/reddit                  # Trigger Reddit ingestion
POST /ingest/social                  # Trigger social media ingestion
GET /task/{task_id}                  # Get task status
```

### Feed Items
```
GET /feed-items                      # List feed items with filtering
GET /stats                           # Get ingestion statistics
```

## Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///./data/feed.db

# Redis
REDIS_URL=redis://localhost:6379/0

# API Keys
PERPLEXITY_API_KEY=your_perplexity_api_key
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
```

## Setup Instructions

### 1. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp ../../env.example .env
# Edit .env with your API keys

# Initialize database
python -c "from shared.database.connection import init_database; init_database()"

# Start Redis (if not running)
redis-server

# Start Celery worker
celery -A celery_app worker --loglevel=info

# Start Celery beat (in another terminal)
celery -A celery_app beat --loglevel=info

# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Docker Deployment

```bash
# Build the image
docker build -t feed-ingestion .

# Run with Redis
docker-compose up -d
```

### 3. Kubernetes Deployment

```bash
# Create namespace
kubectl apply -f ../../k8s/namespace.yaml

# Create secrets (update with your API keys)
kubectl apply -f ../../k8s/secrets/api-keys.yaml

# Deploy Redis
kubectl apply -f ../../k8s/redis/

# Deploy the service
kubectl apply -f ../../k8s/feed-ingestion/
```

## Job Scheduling

The service automatically schedules ingestion jobs:

- **Perplexity**: Every 5 minutes
- **Reddit**: Every 10 minutes  
- **Social Media**: Every 15 minutes

## Database Schema

### Core Tables

1. **data_sources**: Configuration for each data source
2. **feed_items**: Ingested content with metadata
3. **ingestion_jobs**: Job tracking and status
4. **content_cache**: Redis-like caching for API responses
5. **user_categories**: User preferences (shared with main service)

### Key Features

- **Source tracking**: Each feed item is linked to its data source
- **Engagement scoring**: Calculated based on likes, comments, shares
- **Content categorization**: Auto-detected or assigned categories
- **Rate limiting**: Built-in protection against API limits
- **Error handling**: Comprehensive error tracking and retry logic

## Monitoring

### Health Checks
- API health: `GET /health`
- Database connectivity
- Redis connectivity
- Celery worker status

### Metrics
- Total feed items ingested
- Job success/failure rates
- API response times
- Cache hit rates

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Ensure Redis is running
   - Check REDIS_URL environment variable

2. **API Rate Limits**
   - Check rate limit settings in data source configuration
   - Review cache settings

3. **Database Errors**
   - Verify DATABASE_URL
   - Run database initialization

4. **Celery Tasks Not Running**
   - Check Celery worker status
   - Verify Redis connectivity
   - Review task logs

### Logs

```bash
# API logs
kubectl logs -f deployment/feed-ingestion -c feed-ingestion-api

# Celery worker logs
kubectl logs -f deployment/feed-ingestion -c celery-worker

# Celery beat logs
kubectl logs -f deployment/feed-ingestion -c celery-beat
```

## Development

### Adding New Data Sources

1. Create a new runner in `runners/`
2. Add Celery task configuration
3. Update database models if needed
4. Add environment variables
5. Update Kubernetes manifests

### Testing

```bash
# Test individual runners
python runners/perplexity_runner.py
python runners/reddit_runner.py
python runners/social_runner.py

# Test API endpoints
curl http://localhost:8001/health
curl http://localhost:8001/data-sources
```

## Security Considerations

- API keys stored in Kubernetes secrets
- Rate limiting to prevent abuse
- Input validation on all endpoints
- Database connection pooling
- Error messages don't expose sensitive data 