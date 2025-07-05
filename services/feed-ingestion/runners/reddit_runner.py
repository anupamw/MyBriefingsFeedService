import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from dotenv import load_dotenv

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from shared.database.connection import SessionLocal
from shared.models.database_models import DataSource, FeedItem, IngestionJob, ContentCache
from services.feed_ingestion.celery_app import celery_app

load_dotenv()

class RedditRunner:
    """Runner for Reddit API integration"""
    
    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = "MyBriefingsFeedService/1.0"
        self.base_url = "https://oauth.reddit.com"
        self.db = SessionLocal()
        self.access_token = None
        
    def get_data_source(self) -> Optional[DataSource]:
        """Get Reddit data source configuration"""
        return self.db.query(DataSource).filter(
            DataSource.name == "reddit",
            DataSource.is_active == True
        ).first()
    
    def authenticate(self) -> bool:
        """Authenticate with Reddit API"""
        if not self.client_id or not self.client_secret:
            print("Reddit API credentials not found")
            return False
        
        auth_url = "https://www.reddit.com/api/v1/access_token"
        auth_data = {
            "grant_type": "client_credentials"
        }
        headers = {
            "User-Agent": self.user_agent
        }
        
        try:
            response = requests.post(
                auth_url,
                data=auth_data,
                headers=headers,
                auth=(self.client_id, self.client_secret),
                timeout=10
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            return bool(self.access_token)
            
        except requests.exceptions.RequestException as e:
            print(f"Error authenticating with Reddit: {e}")
            return False
    
    def get_subreddit_posts(self, subreddit: str, limit: int = 25, time_filter: str = "day") -> Optional[List[Dict]]:
        """Get trending posts from a subreddit"""
        if not self.access_token:
            if not self.authenticate():
                return None
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": self.user_agent
        }
        
        url = f"{self.base_url}/r/{subreddit}/top"
        params = {
            "limit": limit,
            "t": time_filter  # hour, day, week, month, year, all
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            posts = []
            
            if "data" in data and "children" in data["data"]:
                for post in data["data"]["children"]:
                    post_data = post["data"]
                    
                    # Filter out low-quality posts
                    if (post_data.get("score", 0) < 10 or 
                        post_data.get("num_comments", 0) < 5 or
                        post_data.get("selftext", "").strip() == ""):
                        continue
                    
                    posts.append({
                        "title": post_data.get("title", ""),
                        "content": post_data.get("selftext", ""),
                        "url": f"https://reddit.com{post_data.get('permalink', '')}",
                        "score": post_data.get("score", 0),
                        "num_comments": post_data.get("num_comments", 0),
                        "subreddit": post_data.get("subreddit", ""),
                        "author": post_data.get("author", ""),
                        "created_utc": post_data.get("created_utc", 0),
                        "upvote_ratio": post_data.get("upvote_ratio", 0)
                    })
            
            return posts
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching posts from r/{subreddit}: {e}")
            return None
    
    def get_trending_subreddits(self) -> List[str]:
        """Get list of trending subreddits to monitor"""
        data_source = self.get_data_source()
        if data_source and data_source.config:
            return data_source.config.get("subreddits", [
                "news", "technology", "science", "worldnews", 
                "programming", "MachineLearning", "datascience"
            ])
        return ["news", "technology", "science", "worldnews"]
    
    def calculate_engagement_score(self, post: Dict) -> float:
        """Calculate engagement score for a post"""
        score = post.get("score", 0)
        comments = post.get("num_comments", 0)
        upvote_ratio = post.get("upvote_ratio", 0.5)
        
        # Simple engagement formula
        engagement = (score * 0.4) + (comments * 0.6) + (upvote_ratio * 100)
        return min(engagement, 100.0)  # Cap at 100
    
    def save_feed_items(self, posts: List[Dict], data_source: DataSource) -> Dict[str, int]:
        """Save Reddit posts as feed items"""
        created = 0
        updated = 0
        
        for post in posts:
            try:
                # Check if post already exists (by URL)
                existing_item = self.db.query(FeedItem).filter(
                    FeedItem.url == post.get("url"),
                    FeedItem.data_source_id == data_source.id
                ).first()
                
                engagement_score = self.calculate_engagement_score(post)
                
                if existing_item:
                    # Update existing item
                    existing_item.title = post.get("title", existing_item.title)
                    existing_item.content = post.get("content", existing_item.content)
                    existing_item.engagement_score = engagement_score
                    existing_item.updated_at = datetime.utcnow()
                    existing_item.raw_data = post
                    updated += 1
                else:
                    # Create new item
                    created_utc = post.get("created_utc", 0)
                    published_at = datetime.fromtimestamp(created_utc) if created_utc else datetime.utcnow()
                    
                    feed_item = FeedItem(
                        title=post.get("title", "Untitled"),
                        content=post.get("content", ""),
                        url=post.get("url", ""),
                        source=f"Reddit r/{post.get('subreddit', 'unknown')}",
                        data_source_id=data_source.id,
                        published_at=published_at,
                        engagement_score=engagement_score,
                        raw_data=post,
                        category="Social Media",
                        tags=["reddit", post.get("subreddit", "").lower()]
                    )
                    self.db.add(feed_item)
                    created += 1
                
            except Exception as e:
                print(f"Error saving Reddit post: {e}")
                continue
        
        self.db.commit()
        return {"created": created, "updated": updated}

@celery_app.task(bind=True)
def ingest_reddit(self, subreddits: List[str] = None, time_filter: str = "day"):
    """Celery task for Reddit ingestion"""
    runner = RedditRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("Reddit data source not found or inactive")
        return {"error": "Data source not found"}
    
    if subreddits is None:
        subreddits = runner.get_trending_subreddits()
    
    # Create ingestion job record
    job = IngestionJob(
        job_type="reddit",
        status="running",
        started_at=datetime.utcnow(),
        parameters={"subreddits": subreddits, "time_filter": time_filter},
        data_source_id=data_source.id
    )
    runner.db.add(job)
    runner.db.commit()
    
    total_created = 0
    total_updated = 0
    
    try:
        for i, subreddit in enumerate(subreddits):
            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={"current_subreddit": subreddit, "processed": i + 1, "total": len(subreddits)}
            )
            
            posts = runner.get_subreddit_posts(subreddit, limit=25, time_filter=time_filter)
            if posts:
                results = runner.save_feed_items(posts, data_source)
                total_created += results["created"]
                total_updated += results["updated"]
        
        # Update job record
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.items_created = total_created
        job.items_updated = total_updated
        runner.db.commit()
        
        return {
            "status": "completed",
            "created": total_created,
            "updated": total_updated,
            "subreddits_processed": len(subreddits)
        }
        
    except Exception as e:
        # Update job record with error
        job.status = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = str(e)
        runner.db.commit()
        
        raise self.retry(countdown=60, max_retries=3)
    
    finally:
        runner.db.close()

if __name__ == "__main__":
    # Test the runner
    runner = RedditRunner()
    if runner.authenticate():
        posts = runner.get_subreddit_posts("technology", limit=5)
        print(json.dumps(posts, indent=2))
    else:
        print("Failed to authenticate with Reddit") 