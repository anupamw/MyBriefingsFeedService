# Football Transfers Feed Service

A FastAPI-based web application for football transfer news and feeds, containerized with Docker and designed for deployment on DigitalOcean.

**🚀 Latest Update: GitHub Actions deployment ready!**

## Features

- RESTful API with CRUD operations
- Automatic API documentation (Swagger UI)
- Health check endpoint
- CORS middleware enabled
- Pydantic models for data validation
- Docker containerization
- Automated deployment via GitHub Actions

## Local Development

### Option 1: Docker (Recommended)

1. **Prerequisites**:
   - Docker
   - Docker Compose

2. **Clone the repository**:
```bash
git clone <your-repo-url>
cd MyBriefingsFeedService
```

3. **Run with Docker Compose**:
```bash
docker-compose up --build
```

4. **Or run with Docker directly**:
```bash
docker build -t football-transfers-app .
docker run -p 8000:8000 football-transfers-app
```

The application will be available at `http://localhost:8000`

### Option 2: Local Python Environment

1. **Prerequisites**:
   - Python 3.8+
   - pip

2. **Create virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Run the application**:
```bash
python main.py
```

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

- `GET /` - Welcome message
- `GET /health` - Health check
- `GET /items` - Get all items
- `GET /items/{item_id}` - Get specific item
- `POST /items` - Create new item
- `PUT /items/{item_id}` - Update item
- `DELETE /items/{item_id}` - Delete item

## DigitalOcean Deployment

### Prerequisites

1. **DigitalOcean Account**: Create an account at [digitalocean.com](https://digitalocean.com)
2. **Droplet**: Create a new Ubuntu droplet (recommended: Ubuntu 22.04 LTS)
3. **SSH Key**: Add your SSH key to DigitalOcean for secure access

### Initial Server Setup

1. **Connect to your droplet**:
```bash
ssh root@YOUR_DROPLET_IP
```

2. **Create a non-root user** (recommended):
```bash
adduser fastapi
usermod -aG sudo fastapi
usermod -aG docker fastapi  # Add to docker group
```

3. **Switch to the new user**:
```bash
su - fastapi
```

4. **Run the Docker deployment script**:
```bash
chmod +x deploy-docker.sh
./deploy-docker.sh
```

### Manual Docker Setup (Alternative)

If you prefer manual setup:

1. **Install Docker**:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

2. **Install Docker Compose**:
```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

3. **Create application directory**:
```bash
sudo mkdir -p /var/www/football-transfers-app
sudo chown $USER:$USER /var/www/football-transfers-app
cd /var/www/football-transfers-app
```

4. **Clone repository**:
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git .
```

5. **Build and run Docker container**:
```bash
docker build -t football-transfers-app:latest .
docker run -d \
    --name football-transfers-app \
    --restart unless-stopped \
    -p 8000:8000 \
    football-transfers-app:latest
```

6. **Verify deployment**:
```bash
docker ps
curl http://localhost:8000/health
```

## GitHub Actions Setup

### Required Secrets

Add these secrets to your GitHub repository (`Settings` → `Secrets and variables` → `Actions`):

1. **DIGITALOCEAN_HOST**: Your droplet's IP address
2. **DIGITALOCEAN_USERNAME**: SSH username (usually `fastapi` or `root`)
3. **DIGITALOCEAN_SSH_KEY**: Your private SSH key

### SSH Key Setup

1. **Generate SSH key** (if you don't have one):
```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

2. **Add public key to DigitalOcean**:
   - Go to your droplet's console
   - Add the public key to `~/.ssh/authorized_keys`

3. **Add private key to GitHub**:
   - Copy the private key content
   - Add it as `DIGITALOCEAN_SSH_KEY` secret

### Workflow Features

The GitHub Actions workflow:
- ✅ Runs tests on every push/PR
- ✅ Builds Docker image
- ✅ Deploys automatically when merged to main
- ✅ Includes health checks and error handling
- ✅ Provides detailed deployment logs
- ✅ Cleans up old Docker images

## Docker Commands

### Local Development
```bash
# Build image
docker build -t football-transfers-app .

# Run container
docker run -p 8000:8000 football-transfers-app

# Run with Docker Compose
docker-compose up --build

# View logs
docker logs football-transfers-app

# Shell access
docker exec -it football-transfers-app /bin/bash
```

### Production Management
```bash
# View running containers
docker ps

# Stop container
docker stop football-transfers-app

# Remove container
docker rm football-transfers-app

# Restart container
docker restart football-transfers-app

# View logs
docker logs football-transfers-app

# Clean up old images
docker image prune -f
```

## Environment Variables

For production, consider setting these environment variables in your Docker run command:

```bash
docker run -d \
    --name football-transfers-app \
    --restart unless-stopped \
    -p 8000:8000 \
    -e DATABASE_URL="postgresql://user:password@localhost/dbname" \
    -e SECRET_KEY="your-secret-key-here" \
    -e ALLOWED_ORIGINS="https://yourdomain.com" \
    football-transfers-app:latest
```

## Monitoring and Logs

### View Application Logs
```bash
docker logs football-transfers-app
docker logs -f football-transfers-app  # Follow logs
```

### Check Container Status
```bash
docker ps
docker stats football-transfers-app
```

### Health Check
```bash
curl http://localhost:8000/health
```

## Security Considerations

1. **Firewall**: Configure UFW firewall on your droplet
2. **SSL/TLS**: Set up HTTPS with Let's Encrypt and Nginx reverse proxy
3. **Environment Variables**: Store sensitive data in environment variables
4. **Regular Updates**: Keep your system and Docker images updated
5. **Non-root User**: Run containers as non-root user (already configured)

## Troubleshooting

### Common Issues

1. **Container won't start**:
   ```bash
   docker logs football-transfers-app
   docker run --rm football-transfers-app  # Run interactively
   ```

2. **Port already in use**:
   ```bash
   sudo netstat -tlnp | grep :8000
   docker stop football-transfers-app
   ```

3. **Permission denied**:
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

4. **Build fails**:
   ```bash
   docker build --no-cache -t football-transfers-app .
   ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with Docker: `docker-compose up --build`
5. Submit a pull request

## License

MIT License 