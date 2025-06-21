# Docker Setup Guide

This guide covers the complete Docker setup for the Football Transfers Feed Service.

## 🐳 What's Been Set Up

### 1. **Dockerfile**
- Multi-stage build optimized for production
- Non-root user for security
- Health checks included
- Minimal base image (Python 3.11 slim)

### 2. **Docker Compose**
- **Development**: `docker-compose.yml` - for local development
- **Production**: `docker-compose.prod.yml` - for production deployment

### 3. **GitHub Actions**
- Automated Docker build and deployment
- Health check verification
- Image cleanup

### 4. **Deployment Scripts**
- `deploy-docker.sh` - One-command DigitalOcean setup
- `scripts/dev.sh` - Local development helper

## 🚀 Quick Start

### Local Development
```bash
# Option 1: Docker Compose (Recommended)
docker-compose up --build

# Option 2: Direct Docker
docker build -t football-transfers-app .
docker run -p 8000:8000 football-transfers-app

# Option 3: Development Script
./scripts/dev.sh up
```

### Production Deployment
```bash
# On DigitalOcean droplet
chmod +x deploy-docker.sh
./deploy-docker.sh
```

## 📁 File Structure

```
FootballTransfersFeedService/
├── Dockerfile                 # Main Docker configuration
├── .dockerignore             # Files to exclude from build
├── docker-compose.yml        # Development compose
├── docker-compose.prod.yml   # Production compose
├── deploy-docker.sh          # DigitalOcean deployment script
├── scripts/
│   └── dev.sh               # Local development helper
├── .github/workflows/
│   └── deploy.yml           # GitHub Actions workflow
└── main.py                  # FastAPI application
```

## 🔧 Configuration

### Environment Variables
Set these in your Docker run command or docker-compose:

```bash
# Database (when you add one)
DATABASE_URL=postgresql://user:password@localhost/dbname

# Security
SECRET_KEY=your-secret-key-here

# CORS
ALLOWED_ORIGINS=https://yourdomain.com

# Python
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```

### Docker Run Example
```bash
docker run -d \
    --name football-transfers-app \
    --restart unless-stopped \
    -p 8000:8000 \
    -e SECRET_KEY="your-secret-key" \
    -e ALLOWED_ORIGINS="https://yourdomain.com" \
    football-transfers-app:latest
```

## 🛠️ Development Commands

### Using the Development Script
```bash
./scripts/dev.sh build    # Build image
./scripts/dev.sh run      # Run container
./scripts/dev.sh up       # Start with docker-compose
./scripts/dev.sh down     # Stop docker-compose
./scripts/dev.sh logs     # View logs
./scripts/dev.sh shell    # Access container shell
./scripts/dev.sh clean    # Clean up
./scripts/dev.sh test     # Run tests
```

### Manual Docker Commands
```bash
# Build
docker build -t football-transfers-app .

# Run
docker run -p 8000:8000 football-transfers-app

# View logs
docker logs football-transfers-app

# Shell access
docker exec -it football-transfers-app /bin/bash

# Stop and remove
docker stop football-transfers-app
docker rm football-transfers-app
```

## 🚀 Deployment

### DigitalOcean Setup
1. **Create droplet** (Ubuntu 22.04 LTS)
2. **SSH to droplet**:
   ```bash
   ssh root@YOUR_DROPLET_IP
   ```
3. **Create user and run deployment**:
   ```bash
   adduser fastapi
   usermod -aG sudo fastapi
   usermod -aG docker fastapi
   su - fastapi
   chmod +x deploy-docker.sh
   ./deploy-docker.sh
   ```

### GitHub Actions
The workflow automatically:
1. ✅ Tests the application
2. ✅ Builds Docker image
3. ✅ Deploys to DigitalOcean
4. ✅ Verifies deployment with health checks
5. ✅ Cleans up old images

## 🔍 Monitoring

### Health Checks
```bash
# Application health
curl http://localhost:8000/health

# Container health
docker ps
docker stats football-transfers-app
```

### Logs
```bash
# View logs
docker logs football-transfers-app

# Follow logs
docker logs -f football-transfers-app
```

## 🛡️ Security Features

1. **Non-root user**: Container runs as `appuser`
2. **Minimal base image**: Python slim image
3. **Health checks**: Automatic health monitoring
4. **Environment variables**: Secure configuration
5. **Restart policy**: Automatic recovery

## 🔧 Troubleshooting

### Common Issues

1. **Build fails**:
   ```bash
   docker build --no-cache -t football-transfers-app .
   ```

2. **Container won't start**:
   ```bash
   docker logs football-transfers-app
   docker run --rm football-transfers-app  # Run interactively
   ```

3. **Permission issues**:
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

4. **Port conflicts**:
   ```bash
   docker stop football-transfers-app
   # Or change port: -p 8001:8000
   ```

## 📈 Next Steps

1. **Add database**: Uncomment PostgreSQL in docker-compose.prod.yml
2. **Add Redis**: Uncomment Redis for caching
3. **Add Nginx**: Reverse proxy for SSL termination
4. **Add monitoring**: Prometheus/Grafana setup
5. **Add CI/CD**: More sophisticated deployment pipeline

## 🎯 Benefits of Docker

- ✅ **Consistency**: Same environment everywhere
- ✅ **Isolation**: No conflicts with system packages
- ✅ **Scalability**: Easy to scale horizontally
- ✅ **Portability**: Run anywhere Docker is available
- ✅ **Versioning**: Easy to rollback to previous versions
- ✅ **Security**: Isolated from host system 