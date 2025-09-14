# Local Development Setup

## Prerequisites
- Docker and Docker Compose installed
- API keys for external services

## Setup Steps

### 1. Copy Environment File
```bash
cp env.local.example .env
```

### 2. Edit .env File
Add your actual API keys to the `.env` file:
```bash
# Required API Keys
PERPLEXITY_API_KEY=pplx-your-actual-key-here
NEWS_API_KEY=your-actual-news-api-key

# Optional (for Reddit features)
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
```

### 3. Start All Services
```bash
# Start all services in background
docker-compose -f docker-compose.local.yml up -d

# Or start with build (if you made changes)
docker-compose -f docker-compose.local.yml up --build -d
```

### 4. Check Service Status
```bash
# Check all containers are running
docker-compose -f docker-compose.local.yml ps

# View logs
docker-compose -f docker-compose.local.yml logs

# View logs for specific service
docker-compose -f docker-compose.local.yml logs main-app
```

### 5. Access Services
- **Main App**: http://localhost:8000
- **Feed Ingestion**: http://localhost:8001
- **Database**: localhost:5432
- **API Documentation**: 
  - Main App: http://localhost:8000/docs
  - Ingestion: http://localhost:8001/docs

### 6. Initialize Database
```bash
# Run database migrations (if needed)
docker-compose -f docker-compose.local.yml exec main-app python -c "from shared.database.connection import init_database; init_database()"
```

## Development Workflow

### Making Code Changes
- Code changes are automatically reflected due to volume mounts
- Restart specific service if needed:
```bash
docker-compose -f docker-compose.local.yml restart main-app
```

### Testing Template Changes
1. Make changes to templates/ directory
2. Changes are immediately available (volume mounted)
3. Test at http://localhost:8000

### Stopping Services
```bash
# Stop all services
docker-compose -f docker-compose.local.yml down

# Stop and remove volumes (clears database)
docker-compose -f docker-compose.local.yml down -v
```

## Troubleshooting

### Check Service Health
```bash
# Check health status
docker-compose -f docker-compose.local.yml ps

# View detailed logs
docker-compose -f docker-compose.local.yml logs --tail=50 main-app
```

### Database Issues
```bash
# Connect to database directly
docker-compose -f docker-compose.local.yml exec postgres psql -U fastapi -d briefings_feed

# Reset database
docker-compose -f docker-compose.local.yml down -v
docker-compose -f docker-compose.local.yml up -d
```

### API Key Issues
- Ensure `.env` file exists and has correct API keys
- Check logs for authentication errors
- Verify API keys are valid and have sufficient credits

## Production Deployment
- Local development uses `docker-compose.local.yml`
- Production deployment continues to use GitHub Actions → Kubernetes
- Pushing to `main` branch still deploys to droplet as before

