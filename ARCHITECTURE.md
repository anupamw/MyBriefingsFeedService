# My Briefings Feed Service - Architecture Documentation

## Overview

My Briefings Feed Service is a comprehensive news aggregation and personalization platform that uses AI to curate and summarize content from multiple sources. The system is built with a microservices architecture deployed on Kubernetes with automated CI/CD pipelines.

## 1. Software Architecture

### Core Services

The system consists of **4 main services**:

#### 1.1 Main Application Service (Port 8000)
- **Technology**: FastAPI with Python 3.11
- **Purpose**: Primary web application serving user interface and core APIs
- **Key Features**:
  - User authentication and authorization (JWT-based)
  - Feed display and management
  - AI summary generation and storage
  - User category management
  - Real-time feed updates

#### 1.2 Feed Ingestion Service (Port 8001)
- **Technology**: FastAPI with Celery workers
- **Purpose**: Data collection and processing from external sources
- **Key Features**:
  - Multi-source data ingestion (Perplexity AI, NewsAPI, Reddit, Social Media)
  - Background job processing with Celery
  - AI-powered content relevance filtering
  - Scheduled data collection
  - Content caching and rate limiting

#### 1.3 Celery Worker Service
- **Technology**: Celery with PostgreSQL broker
- **Purpose**: Asynchronous task processing
- **Key Features**:
  - Background AI summary generation
  - Feed ingestion tasks
  - Content processing and filtering
  - Scheduled cleanup tasks

#### 1.4 Celery Beat Service
- **Technology**: Celery Beat scheduler
- **Purpose**: Task scheduling and cron-like functionality
- **Key Features**:
  - Scheduled feed ingestion
  - Periodic cleanup tasks
  - Health monitoring tasks

### Data Flow Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Main App      │    │  Ingestion      │    │  Celery Worker  │
│   (Port 8000)   │◄──►│  Service        │◄──►│  (Background)   │
│                 │    │  (Port 8001)    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                          │
│  • Users & Authentication  • Feed Items  • Categories          │
│  • AI Summaries           • Ingestion Jobs  • Data Sources     │
└─────────────────────────────────────────────────────────────────┘
         ▲
         │
┌─────────────────┐
│  Celery Beat    │
│  (Scheduler)    │
└─────────────────┘
```

## 2. Key APIs

### 2.1 Main Application APIs (Port 8000)

#### Authentication APIs
- `POST /auth/signup` - User registration
- `POST /auth/login` - User authentication
- `GET /auth/me` - Get current user info

#### Feed Management APIs
- `GET /feed` - Get personalized feed items
- `GET /feed/{item_id}` - Get specific feed item
- `POST /feed/refresh` - Trigger feed refresh

#### User Category APIs
- `GET /user/categories` - Get user's categories
- `POST /user/categories` - Create new category
- `PUT /user/categories/{id}` - Update category
- `DELETE /user/categories/{id}` - Delete category

#### AI Summary APIs
- `POST /ai-summary/generate/{user_id}` - Generate AI summary (sync)
- `POST /ai-summary/generate-background/{user_id}` - Generate AI summary (async)
- `GET /ai-summary/latest` - Get latest AI summary
- `GET /ai-summary/status/{user_id}` - Check summary generation status

#### Debug APIs
- `GET /debug/filtering-stats/{user_id}` - Get relevance filtering statistics
- `GET /debug/cleanup-status` - Get cleanup task status

### 2.2 Feed Ingestion APIs (Port 8001)

#### Data Source Management
- `GET /data-sources` - List all data sources
- `POST /data-sources` - Create new data source
- `PUT /data-sources/{id}/toggle` - Toggle source active status

#### Ingestion Control
- `POST /ingest/perplexity` - Trigger Perplexity AI ingestion
- `POST /ingest/newsapi/user/{user_id}` - Trigger NewsAPI ingestion
- `POST /ingest/reddit` - Trigger Reddit ingestion
- `POST /ingest/social` - Trigger social media ingestion

#### Job Management
- `GET /ingestion-jobs` - List ingestion jobs
- `GET /task/{task_id}` - Get task status
- `GET /stats` - Get ingestion statistics

#### Health & Debug
- `GET /ingestion/health` - Service health check
- `GET /debug/perplexity-history` - Perplexity API call history

## 3. Deployment Architecture

### 3.1 Kubernetes Setup

#### Namespace Configuration
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-briefings
```

#### Main Application Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-briefings-app
  namespace: my-briefings
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-briefings-app
  template:
    spec:
      containers:
      - name: my-briefings-app
        image: my-briefings-app:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: "postgresql://fastapi:password@64.227.134.87:5432/briefings_feed"
        - name: PERPLEXITY_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: perplexity-api-key
```

#### Ingestion Service Deployment
```yaml
# k8s/ingestion-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-briefings-ingestion
  namespace: my-briefings
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: my-briefings-ingestion
        image: my-briefings-ingestion:latest
        ports:
        - containerPort: 8001
        env:
        - name: ENABLE_POST_PROCESSING_NEWSAPI
          value: "true"
        - name: ENABLE_POST_PROCESSING_PERPLEXITY
          value: "true"
```

#### Celery Services
```yaml
# k8s/celery-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-briefings-celery-worker
  namespace: my-briefings
spec:
  template:
    spec:
      containers:
      - name: celery-worker
        image: my-briefings-ingestion:latest
        command: ["celery", "-A", "celery_app", "worker", "--loglevel=info"]

# k8s/celery-beat-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-briefings-celery-beat
  namespace: my-briefings
spec:
  template:
    spec:
      containers:
      - name: celery-beat
        image: my-briefings-ingestion:latest
        command: ["celery", "-A", "celery_app", "beat", "--loglevel=info"]
```

### 3.2 Service Configuration

#### Service Definitions
```yaml
# k8s/service.yaml - Main App Service
apiVersion: v1
kind: Service
metadata:
  name: my-briefings-service
  namespace: my-briefings
spec:
  type: NodePort
  ports:
  - port: 8000
    targetPort: 8000
    nodePort: 30100
  selector:
    app: my-briefings-app

# k8s/ingestion-service.yaml - Ingestion Service
apiVersion: v1
kind: Service
metadata:
  name: my-briefings-ingestion-service
  namespace: my-briefings
spec:
  type: NodePort
  ports:
  - port: 8001
    targetPort: 8001
    nodePort: 30101
  selector:
    app: my-briefings-ingestion
```

#### Ingress Configuration
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-briefings-ingress
  namespace: my-briefings
  annotations:
    kubernetes.io/ingress.class: "traefik"
spec:
  rules:
  - host: 64.227.134.87.nip.io
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-briefings-service
            port:
              number: 8000
      - path: /ingestion
        pathType: Prefix
        backend:
          service:
            name: my-briefings-ingestion-service
            port:
              number: 8001
```

### 3.3 External PostgreSQL Database

#### Docker Compose Configuration
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: briefings_feed
      POSTGRES_USER: fastapi
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

#### Database Connection
- **Host**: External PostgreSQL running on Docker
- **Port**: 5432
- **Database**: briefings_feed
- **User**: fastapi
- **Connection String**: `postgresql://fastapi:password@64.227.134.87:5432/briefings_feed`

### 3.4 Secrets Management

#### API Keys Secret
```yaml
# k8s/secrets/api-keys.yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-keys
  namespace: my-briefings
type: Opaque
data:
  perplexity-api-key: <base64-encoded-key>
  news-api-key: <base64-encoded-key>
```

## 4. Build and CI/CD Pipeline

### 4.1 GitHub Actions Workflow

#### Main Deployment Workflow (`.github/workflows/deploy.yml`)

```yaml
name: Deploy to k3s

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

env:
  DROPLET_IP: ${{ secrets.DIGITALOCEAN_HOST }}
  DROPLET_USER: root
  SSH_PRIVATE_KEY: ${{ secrets.DIGITALOCEAN_SSH_KEY }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r services/feed-ingestion/requirements.txt
    
    - name: Validate Python imports
      run: |
        python -c "from main import app; print('✅ Main app imports successful')"
        python -c "from services.feed_ingestion.main import app; print('✅ Ingestion service imports successful')"

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Build Docker images
      run: |
        docker build --platform linux/amd64 -t my-briefings-app:latest .
        docker build --platform linux/amd64 -t my-briefings-ingestion:latest -f ./services/feed-ingestion/Dockerfile .
    
    - name: Save Docker images
      run: |
        docker save my-briefings-app:latest -o my-briefings-app.tar
        docker save my-briefings-ingestion:latest -o my-briefings-ingestion.tar
    
    - name: Deploy to droplet
      run: |
        # Setup SSH
        mkdir -p ~/.ssh
        echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
        chmod 600 ~/.ssh/id_rsa
        ssh-keyscan -H $DROPLET_IP >> ~/.ssh/known_hosts
        
        # Transfer images
        scp my-briefings-app.tar $DROPLET_USER@$DROPLET_IP:/tmp/
        scp my-briefings-app.tar $DROPLET_USER@$DROPLET_IP:/tmp/
        
        # Deploy on droplet
        ssh $DROPLET_USER@$DROPLET_IP "
          docker load -i /tmp/my-briefings-app.tar
          docker load -i /tmp/my-briefings-ingestion.tar
          kubectl apply -f k8s/
          kubectl rollout restart deployment/my-briefings-app -n my-briefings
          kubectl rollout restart deployment/my-briefings-ingestion -n my-briefings
        "
```

### 4.2 Docker Build Configuration

#### Main Application Dockerfile
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Ingestion Service Dockerfile
```dockerfile
# services/feed-ingestion/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy shared components
COPY shared/ ./shared/
COPY services/feed-ingestion/ ./

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 4.3 Deployment Process

#### Automated Deployment Steps
1. **Code Push**: Developer pushes to `main` branch
2. **GitHub Actions Trigger**: Workflow starts automatically
3. **Testing Phase**: 
   - Python dependency installation
   - Import validation
   - Basic functionality tests
4. **Build Phase**:
   - Docker image creation for both services
   - Multi-platform build support (linux/amd64)
   - Image optimization and compression
5. **Deployment Phase**:
   - SSH connection to DigitalOcean droplet
   - Docker image transfer
   - Kubernetes deployment update
   - Service restart and health checks

#### Manual Deployment Commands
```bash
# Build images locally
docker build -t my-briefings-app:latest .
docker build -t my-briefings-ingestion:latest -f ./services/feed-ingestion/Dockerfile .

# Deploy to Kubernetes
kubectl apply -f k8s/
kubectl rollout restart deployment/my-briefings-app -n my-briefings
kubectl rollout restart deployment/my-briefings-ingestion -n my-briefings

# Check deployment status
kubectl get pods -n my-briefings
kubectl get services -n my-briefings
```

### 4.4 Environment Configuration

#### Required GitHub Secrets
- `DIGITALOCEAN_HOST`: IP address of the deployment droplet
- `DIGITALOCEAN_SSH_KEY`: Private SSH key for droplet access

#### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://fastapi:password@64.227.134.87:5432/briefings_feed

# API Keys
PERPLEXITY_API_KEY=pplx-...
NEWS_API_KEY=...

# Service Configuration
ENABLE_POST_PROCESSING_NEWSAPI=true
ENABLE_POST_PROCESSING_PERPLEXITY=true
SECRET_KEY=your-super-secret-key-change-this-in-production
```

## 5. Data Sources and Integration

### 5.1 External APIs
- **Perplexity AI**: AI-generated summaries and content analysis
- **NewsAPI**: News articles from various sources
- **Reddit API**: Social media content and discussions
- **RSS Feeds**: TechCrunch, BBC News, Hacker News, etc.

### 5.2 AI-Powered Features
- **Content Relevance Filtering**: AI determines article relevance to user categories
- **Intelligent Summarization**: Perplexity AI generates personalized briefings
- **Content Curation**: Automated selection of high-quality content

## 6. Monitoring and Observability

### 6.1 Health Checks
- Application health endpoints (`/health`, `/ingestion/health`)
- Kubernetes liveness and readiness probes
- Database connection monitoring

### 6.2 Logging
- Structured logging across all services
- Real-time log aggregation with `log-aggregator.sh`
- Debug endpoints for troubleshooting

### 6.3 Metrics
- Ingestion job statistics
- API call history and performance
- Content filtering effectiveness metrics

## 7. Security Considerations

### 7.1 Authentication
- JWT-based authentication
- Password hashing with bcrypt
- Secure token management

### 7.2 API Security
- CORS configuration
- Input validation with Pydantic
- Rate limiting on external API calls

### 7.3 Infrastructure Security
- Kubernetes secrets for sensitive data
- Network policies and service isolation
- Regular security updates via CI/CD

---

This architecture provides a robust, scalable foundation for personalized news aggregation with AI-powered content curation and summarization capabilities.

