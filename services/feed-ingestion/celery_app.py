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
        "runners.social_runner",
        "runners.newsapi_runner",
        "runners.cleanup_runner"
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
        "ingest-newsapi-all-users": {
            "task": "runners.newsapi_runner.ingest_newsapi_for_all_users",
            "schedule": 21600.0,  # Every 6 hours (6 * 60 * 60 seconds)
        },
        "ingest-reddit-all-users": {
            "task": "runners.reddit_runner.ingest_reddit_for_all_users",
            "schedule": 21600.0,  # Every 6 hours (6 * 60 * 60 seconds)
        },
        # Cleanup tasks
        "cleanup-old-feed-items": {
            "task": "runners.cleanup_runner.cleanup_old_feed_items",
            "schedule": 10800.0,  # Every 3 hours (3 * 60 * 60 seconds) - BACK TO NORMAL
            "args": [24]  # Delete items older than 24 hours
        },
        # Disabled runners - uncomment to enable
        # "ingest-reddit": {
        #     "task": "runners.reddit_runner.ingest_reddit",
        #     "schedule": 600.0,  # Every 10 minutes
        # },
        # "ingest-social": {
        #     "task": "runners.social_runner.ingest_social",
        #         "schedule": 900.0,  # Every 15 minutes
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

@celery_app.task(name="generate_ai_summary")
def generate_ai_summary_task(user_id: int, max_words: int = 300):
    """Celery task to generate AI summary for a user"""
    try:
        # Import here to avoid circular imports
        import requests
        import json
        import os
        from datetime import datetime
        from shared.database.connection import SessionLocal
        from shared.models.database_models import UserCategory, FeedItem
        
        # Create a database session for the task
        db = SessionLocal()
        
        try:
            # Get user's active categories
            user_categories = db.query(UserCategory).filter(
                UserCategory.user_id == user_id,
                UserCategory.is_active == True
            ).all()
            
            if not user_categories:
                return {
                    "status": "error",
                    "user_id": user_id,
                    "error": f"No active categories found for user {user_id}"
                }
            
            # Get feed items for user's categories (only relevant items)
            category_names = [cat.category_name for cat in user_categories]
            feed_items = db.query(FeedItem).filter(
                FeedItem.category.in_(category_names),
                FeedItem.is_relevant == True
            ).order_by(FeedItem.published_at.desc()).limit(100).all()
            
            if not feed_items:
                return {
                    "status": "error",
                    "user_id": user_id,
                    "error": f"No relevant feed items found for user {user_id}"
                }
            
            # Group feed items by category
            category_feed_data = {}
            for category in user_categories:
                category_items = [item for item in feed_items if item.category == category.category_name]
                if category_items:
                    category_feed_data[category.category_name] = [
                        {
                            "title": item.title,
                            "summary": item.summary,
                            "source": item.source,
                            "published_at": item.published_at.isoformat() if item.published_at else None,
                            "url": item.url
                        }
                        for item in category_items[:20]  # Limit to 20 items per category
                    ]
            
            # Create the JSON structure for Perplexity
            feed_summary_data = {
                "user_categories": list(category_feed_data.keys()),
                "feed_items_by_category": category_feed_data
            }
            
            # Generate the prompt for Perplexity
            prompt = f"""Given this JSON structure that is organized by the topic category and news items on that category, generate a summarization for the user to read as a briefing. The summary should be up to {max_words} words long.

JSON Structure:
{json.dumps(feed_summary_data, indent=2)}

Please provide a comprehensive yet concise summary that:
1. Highlights the most important developments across all categories
2. Identifies any emerging trends or patterns
3. Provides context for why these items matter
4. Is written in a professional briefing format
5. Stays within the {max_words} word limit

Respond with a well-structured summary that flows naturally between topics."""
            
            # Call Perplexity API
            perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
            if not perplexity_api_key:
                return {
                    "status": "error",
                    "user_id": user_id,
                    "error": "PERPLEXITY_API_KEY not configured"
                }
            
            headers = {
                "Authorization": f"Bearer {perplexity_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are an expert news analyst and briefing writer. Your task is to create concise, informative summaries of news items organized by category. Focus on clarity, relevance, and actionable insights."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.3
            }
            
            perplexity_url = "https://api.perplexity.ai/chat/completions"
            response = requests.post(perplexity_url, headers=headers, json=payload, timeout=30)
            
            if not response.ok:
                return {
                    "status": "error",
                    "user_id": user_id,
                    "error": f"Perplexity API error: {response.status_code} - {response.text}"
                }
            
            result = response.json()
            if "choices" not in result or not result["choices"]:
                return {
                    "status": "error",
                    "user_id": user_id,
                    "error": "Invalid response from Perplexity API"
                }
            
            summary_content = result["choices"][0]["message"]["content"]
            
            # Count actual words in the summary
            actual_word_count = len(summary_content.split())
            
            return {
                "status": "success",
                "user_id": user_id,
                "summary": summary_content,
                "word_count": actual_word_count,
                "max_words_requested": max_words,
                "categories_covered": list(category_feed_data.keys()),
                "total_feed_items_analyzed": len(feed_items),
                "generated_at": datetime.utcnow().isoformat(),
                "source": "Perplexity AI"
            }
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[ERROR] Celery task failed to generate AI summary for user {user_id}: {e}")
        return {
            "status": "error",
            "user_id": user_id,
            "error": str(e)
        }

if __name__ == "__main__":
    celery_app.start() 