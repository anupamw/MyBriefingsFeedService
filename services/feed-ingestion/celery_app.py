import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PostgreSQL configuration for Celery
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fastapi:password@localhost:5432/briefings_feed")

# Create Celery app with PostgreSQL as broker and backend
celery_app = Celery(
    "feed_ingestion",
    broker=f"sqla+{DATABASE_URL}",
    backend=f"db+{DATABASE_URL}",
    include=[
        "runners.perplexity_runner",
        "runners.reddit_runner",
        "runners.social_runner"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Disable eager execution for production/distributed mode
    task_always_eager=False,  # Must be False so tasks are sent to the broker
    task_eager_propagates=True,
    # Task routing
    task_routes={
        "runners.*": {"queue": "celery"},  # Use default queue
    },
    
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Task execution
    # task_always_eager is set above for testing
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,        # 10 minutes
    
    # Result backend
    result_expires=3600,  # 1 hour
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "ingest-perplexity-all-users": {
            "task": "runners.perplexity_runner.ingest_perplexity_for_all_users",
            "schedule": 21600.0,  # Every 6 hours (6 * 60 * 60 seconds)
        },
        # Disabled runners - uncomment to enable
        # "ingest-reddit": {
        #     "task": "runners.reddit_runner.ingest_reddit",
        #     "schedule": 600.0,  # Every 10 minutes
        # },
        # "ingest-social": {
        #     "task": "runners.social_runner.ingest_social",
        #     "schedule": 900.0,  # Every 15 minutes
        # },
    },
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
)

# Task result configuration
celery_app.conf.result_backend_transport_options = {
    "master_name": "mymaster",
    "visibility_timeout": 3600,
}

if __name__ == "__main__":
    celery_app.start() 