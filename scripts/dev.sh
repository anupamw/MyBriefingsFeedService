#!/bin/bash

# Development script for MyBriefingsFeedService
# This script helps with local development using Docker

set -e

echo "🚀 MyBriefingsFeedService - Development Script"

# Function to show usage
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build     - Build Docker image"
    echo "  run       - Run container"
    echo "  up        - Start with docker-compose"
    echo "  down      - Stop docker-compose"
    echo "  logs      - View logs"
    echo "  shell     - Access container shell"
    echo "  clean     - Clean up containers and images"
    echo "  test      - Run tests"
    echo "  help      - Show this help"
}

# Function to build image
build() {
    echo "🔨 Building Docker image..."
    docker build -t my-briefings-app:latest .
    echo "✅ Build completed!"
}

# Function to run container
run() {
    echo "🚀 Running container..."
    docker run -d \
        --name my-briefings-app \
        -p 8000:8000 \
        my-briefings-app:latest
    echo "✅ Container started! App available at http://localhost:8000"
}

# Function to start with docker-compose
up() {
    echo "🚀 Starting with docker-compose..."
    docker-compose up --build -d
    echo "✅ Services started! App available at http://localhost:8000"
}

# Function to stop docker-compose
down() {
    echo "🛑 Stopping docker-compose..."
    docker-compose down
    echo "✅ Services stopped!"
}

# Function to view logs
logs() {
    echo "📋 Viewing logs..."
    docker logs -f my-briefings-app
}

# Function to access shell
shell() {
    echo "🐚 Accessing container shell..."
    docker exec -it my-briefings-app /bin/bash
}

# Function to clean up
clean() {
    echo "🧹 Cleaning up..."
    docker stop my-briefings-app 2>/dev/null || true
    docker rm my-briefings-app 2>/dev/null || true
    docker image prune -f
    echo "✅ Cleanup completed!"
}

# Function to run tests
test() {
    echo "🧪 Running tests..."
    docker run --rm my-briefings-app:latest python -c "
import fastapi
import uvicorn
from main import app
print('✅ FastAPI version:', fastapi.__version__)
print('✅ Uvicorn version:', uvicorn.__version__)
print('✅ App imported successfully')
"
}

# Main script logic
case "${1:-help}" in
    build)
        build
        ;;
    run)
        run
        ;;
    up)
        up
        ;;
    down)
        down
        ;;
    logs)
        logs
        ;;
    shell)
        shell
        ;;
    clean)
        clean
        ;;
    test)
        test
        ;;
    help|*)
        show_usage
        ;;
esac 