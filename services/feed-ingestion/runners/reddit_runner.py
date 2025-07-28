import os
import requests
import json
import time
import feedparser
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from shared.database.connection import SessionLocal, engine
from shared.models.database_models import DataSource, FeedItem, IngestionJob
from celery_app import celery_app

load_dotenv()

# In-memory Reddit call history for debugging
REDDIT_HISTORY_LIMIT = 100

Base = declarative_base()

class RedditCallHistory(Base):
    __tablename__ = "reddit_call_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    subreddit = Column(String(140))
    url = Column(String(500))
    response_status_code = Column(Integer)
    posts_found = Column(Integer)
    posts_saved = Column(Integer)
    error_message = Column(Text, nullable=True)
    response_content = Column(Text, nullable=True)  # Store response text for debugging

# Ensure table exists (run at import)
Base.metadata.create_all(bind=engine)

def add_reddit_history_db(subreddit, url, response_status_code, posts_found, posts_saved, error_message=None, response_content=None):
    print(f"[DEBUG] Attempting to log Reddit call: subreddit={subreddit}, url={url[:60]}, status={response_status_code}, posts_found={posts_found}, posts_saved={posts_saved}")
    db = SessionLocal()
    try:
        record = RedditCallHistory(
            timestamp=datetime.utcnow(),
            subreddit=subreddit,
            url=url,
            response_status_code=response_status_code,
            posts_found=posts_found,
            posts_saved=posts_saved,
            error_message=error_message,
            response_content=response_content
        )
        db.add(record)
        db.commit()
        print(f"[DEBUG] Successfully logged Reddit call to DB (id={record.id})")
    except Exception as e:
        print(f"[ERROR] Failed to log Reddit call: {e}")
    finally:
        db.close()

class RedditRunner:
    """Runner for Reddit API integration"""
    def __init__(self):
        self.user_agent = "python:MyBriefingsFeedService:v1.0"
        self.base_url = "https://www.reddit.com"
        self.db = SessionLocal()

    def parse_html_content(self, html_content: str) -> str:
        """Parse HTML content and extract clean text"""
        if not html_content:
            return ""
        
        # Remove HTML tags using regex
        # First, remove script and style tags and their content
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags but preserve line breaks
        html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</p>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<p[^>]*>', '', html_content, flags=re.IGNORECASE)
        
        # Remove all other HTML tags
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        html_content = html_content.replace('&amp;', '&')
        html_content = html_content.replace('&lt;', '<')
        html_content = html_content.replace('&gt;', '>')
        html_content = html_content.replace('&quot;', '"')
        html_content = html_content.replace('&#39;', "'")
        html_content = html_content.replace('&nbsp;', ' ')
        html_content = html_content.replace('&#32;', ' ')
        
        # Remove Reddit-specific metadata patterns
        # Remove "submitted by /u/username" patterns
        html_content = re.sub(r'submitted by\s+/u/[^\s]+', '', html_content, flags=re.IGNORECASE)
        # Remove "[link]" and "[comments]" patterns
        html_content = re.sub(r'\[link\]', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'\[comments\]', '', html_content, flags=re.IGNORECASE)
        # Remove any remaining Reddit user references
        html_content = re.sub(r'/u/[^\s]+', '', html_content)
        # Remove any remaining Reddit subreddit references
        html_content = re.sub(r'/r/[^\s]+', '', html_content)
        
        # Clean up whitespace and extra spaces
        html_content = re.sub(r'\n\s*\n', '\n\n', html_content)  # Remove extra blank lines
        html_content = re.sub(r'[ \t]+', ' ', html_content)  # Normalize spaces
        html_content = re.sub(r'\s+', ' ', html_content)  # Replace multiple spaces with single space
        html_content = html_content.strip()
        
        # Remove any leading/trailing punctuation that might be left
        html_content = re.sub(r'^[^\w]*', '', html_content)  # Remove leading non-word chars
        html_content = re.sub(r'[^\w]*$', '', html_content)  # Remove trailing non-word chars
        
        return html_content

    def get_top_comment(self, subreddit, post_id):
        url = f'{self.base_url}/r/{subreddit}/comments/{post_id}.json?limit=1'
        headers = {'User-Agent': self.user_agent}
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if len(data) > 1 and data[1]['data']['children']:
            top_comment = data[1]['data']['children'][0]['data']
            return {
                'author': top_comment.get('author'),
                'text': top_comment.get('body')
            }
        return None

    def get_subreddit_posts_with_comments(self, subreddit, limit=3, time_filter='day'):
        # Use JSON API directly (much cleaner data than RSS)
        url = f'{self.base_url}/r/{subreddit}/top.json?limit={limit}&t={time_filter}'
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        print(f"[DEBUG] Fetching Reddit posts from: {url}")
        resp = requests.get(url, headers=headers)
        print(f"[DEBUG] Reddit API response status: {resp.status_code}")
        
        posts = []
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'children' in data['data']:
                print(f"[DEBUG] Found {len(data['data']['children'])} posts in response")
                for post in data['data']['children']:
                    post_data = post['data']
                    post_id = post_data['id']
                    
                    # Get clean post content (selftext is the actual post content)
                    post_content = post_data.get('selftext', '')
                    if not post_content and post_data.get('is_self', False):
                        # If it's a self post but no selftext, use title as content
                        post_content = post_data.get('title', '')
                    
                    # Get top comment if available
                    top_comment = self.get_top_comment(subreddit, post_id)
                    
                    print(f"[DEBUG] Post '{post_data.get('title', '')}': content length = {len(post_content)}")
                    
                    posts.append({
                        'title': post_data.get('title', ''),
                        'summary': post_content,  # Clean post content, no HTML parsing needed
                        'score': post_data.get('score', 0),
                        'url': f"https://reddit.com{post_data.get('permalink', '')}",
                        'subreddit': subreddit,
                        'created_utc': post_data.get('created_utc', 0),
                        'top_comment': top_comment
                    })
            else:
                print(f"[DEBUG] No posts found in Reddit response")
            
            # Log successful JSON API call
            add_reddit_history_db(
                subreddit=subreddit,
                url=url,
                response_status_code=resp.status_code,
                posts_found=len(data.get('data', {}).get('children', [])) if resp.status_code == 200 else 0,
                posts_saved=len(posts),
                response_content=resp.text[:1000] if resp.text else None
            )
        else:
            print(f"[DEBUG] Reddit API error: {resp.text[:200]}")
            # Log failed API call
            add_reddit_history_db(
                subreddit=subreddit,
                url=url,
                response_status_code=resp.status_code,
                posts_found=0,
                posts_saved=0,
                error_message=resp.text[:500] if resp.text else "No response text",
                response_content=resp.text[:1000] if resp.text else None
            )
        
        return posts

    def save_feed_items_with_comments(self, posts: list, data_source, user_category_name=None):
        created = 0
        print(f"[DEBUG] Starting to save {len(posts)} Reddit posts")
        print(f"[DEBUG] Database connection info: {self.db.bind.url}")
        print(f"[DEBUG] User category name: {user_category_name}")
        
        for post in posts:
            try:
                # Truncate title to fit database field
                title = post.get("title", "Untitled")
                if len(title) > 500:
                    title = title[:497] + "..."
                
                # Use user's category name if provided, otherwise use subreddit name
                category = user_category_name if user_category_name else post.get('subreddit', 'Reddit')
                
                feed_item = FeedItem(
                    title=title,
                    summary=post.get("summary", ""),
                    content=post['top_comment']['text'] if post.get('top_comment') else "",
                    url=post.get("url", ""),
                    source=f"Reddit r/{post.get('subreddit', 'unknown')}",
                    data_source_id=data_source.id,
                    published_at=datetime.fromtimestamp(post.get("created_utc", datetime.utcnow().timestamp())),
                    engagement_score=post.get("score", 0),
                    raw_data=post,
                    category=category,
                    tags=["reddit", post.get("subreddit", "").lower()]
                )
                print(f"[DEBUG] Saving Reddit post: '{feed_item.title}' with category '{feed_item.category}'")
                print(f"[DEBUG] Feed item details: source='{feed_item.source}', url='{feed_item.url[:50]}...'")
                
                self.db.add(feed_item)
                created += 1
                print(f"[DEBUG] Added feed item to session (created={created})")
                
            except Exception as e:
                print(f"[ERROR] Error saving Reddit post: {e}")
                import traceback
                print(f"[ERROR] Traceback: {traceback.format_exc()}")
                continue
        
        try:
            print(f"[DEBUG] Committing {created} posts to database...")
            self.db.commit()
            print(f"[DEBUG] Successfully committed {created} Reddit posts to database")
            
            # Verify the posts were actually saved
            if created > 0:
                recent_posts = self.db.query(FeedItem).filter(
                    FeedItem.source.like('%Reddit%'),
                    FeedItem.category == (user_category_name if user_category_name else 'Reddit')
                ).order_by(FeedItem.created_at.desc()).limit(created).all()
                
                print(f"[DEBUG] Verification: Found {len(recent_posts)} posts in database after commit")
                for post in recent_posts:
                    print(f"[DEBUG] Verified post: ID={post.id}, title='{post.title[:50]}...', category='{post.category}'")
            
        except Exception as e:
            print(f"[ERROR] Error committing to database: {e}")
            import traceback
            print(f"[ERROR] Commit traceback: {traceback.format_exc()}")
            self.db.rollback()
            return {"created": 0, "error": str(e)}
            
        return {"created": created}

@celery_app.task(bind=True)
def ingest_reddit(self, subreddits: list = None, time_filter: str = "day"):
    runner = RedditRunner()
    data_source = runner.db.query(DataSource).filter(DataSource.name == "reddit").first()
    print(f"[DEBUG] Reddit data source found: {data_source is not None}")
    if data_source:
        print(f"[DEBUG] Data source ID: {data_source.id}, Name: {data_source.name}, Active: {data_source.is_active}")
    if not data_source:
        print("Reddit data source not found or inactive")
        return {"error": "Data source not found"}
    
    print(f"[DEBUG] Reddit ingestion started with subreddits: {subreddits}")
    
    # Handle None subreddits
    if subreddits is None:
        subreddits = []
    
    total_created = 0
    for subreddit in subreddits:
        print(f"[DEBUG] Processing subreddit: {subreddit}")
        posts = runner.get_subreddit_posts_with_comments(subreddit, limit=3, time_filter=time_filter)
        print(f"[DEBUG] Got {len(posts)} posts from r/{subreddit}")
        if posts:
            results = runner.save_feed_items_with_comments(posts, data_source)
            total_created += results["created"]
            print(f"[DEBUG] Saved {results['created']} posts from r/{subreddit}")
        else:
            print(f"[DEBUG] No posts found for r/{subreddit}")
        
        # Add delay between requests to avoid rate limiting
        time.sleep(2)
    
    runner.db.close()
    print(f"[DEBUG] Reddit ingestion completed: {total_created} total posts created")
    return {"status": "completed", "created": total_created, "subreddits_processed": len(subreddits)}

@celery_app.task(bind=True)
def ingest_reddit_with_category(self, subreddits: list = None, category_name: str = None, time_filter: str = "day"):
    """Ingest Reddit posts and save them with a specific category name"""
    print(f"[DEBUG] ===== Starting ingest_reddit_with_category =====")
    print(f"[DEBUG] Parameters: subreddits={subreddits}, category_name={category_name}, time_filter={time_filter}")
    
    runner = RedditRunner()
    print(f"[DEBUG] RedditRunner created with database: {runner.db.bind.url}")
    
    data_source = runner.db.query(DataSource).filter(DataSource.name == "reddit").first()
    print(f"[DEBUG] Reddit data source found: {data_source is not None}")
    if data_source:
        print(f"[DEBUG] Data source ID: {data_source.id}, Name: {data_source.name}, Active: {data_source.is_active}")
    if not data_source:
        print("Reddit data source not found or inactive")
        return {"error": "Data source not found"}
    
    print(f"[DEBUG] Reddit ingestion started with subreddits: {subreddits}, category: {category_name}")
    
    # Handle None subreddits
    if subreddits is None:
        subreddits = []
    
    total_created = 0
    for subreddit in subreddits:
        print(f"[DEBUG] Processing subreddit: {subreddit} for category: {category_name}")
        posts = runner.get_subreddit_posts_with_comments(subreddit, limit=3, time_filter=time_filter)
        print(f"[DEBUG] Got {len(posts)} posts from r/{subreddit}")
        if posts:
            results = runner.save_feed_items_with_comments(posts, data_source, category_name)
            total_created += results["created"]
            print(f"[DEBUG] Saved {results['created']} posts from r/{subreddit} with category '{category_name}'")
        else:
            print(f"[DEBUG] No posts found for r/{subreddit}")
        
        # Add delay between requests to avoid rate limiting
        time.sleep(2)
    
    runner.db.close()
    print(f"[DEBUG] Reddit ingestion completed: {total_created} total posts created for category '{category_name}'")
    print(f"[DEBUG] ===== Finished ingest_reddit_with_category =====")
    return {"status": "completed", "created": total_created, "subreddits_processed": len(subreddits), "category": category_name}

@celery_app.task(bind=True)
def ingest_reddit_for_user(self, user_id: int):
    """Trigger Reddit ingestion for a specific user based on their categories"""
    from shared.models.database_models import UserCategory
    import json
    db = SessionLocal()
    user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    
    if not user_categories:
        db.close()
        return {"status": "no_categories", "user_id": user_id}
    
    # Process each user category separately
    for user_category in user_categories:
        if user_category.subreddits:
            try:
                subreddits = json.loads(user_category.subreddits)
                # Remove 'r/' prefix if present and deduplicate
                clean_subreddits = list(set([sub.replace('r/', '') for sub in subreddits]))
                
                # Use short_summary for category if available, otherwise fallback to category_name
                category_for_saving = user_category.short_summary if user_category.short_summary else user_category.category_name
                
                # Call ingest_reddit_with_category for each category
                ingest_reddit_with_category.apply_async(args=[clean_subreddits, category_for_saving])
                print(f"[DEBUG] Scheduled Reddit ingestion for user {user_id}, category '{user_category.category_name}' (saving as '{category_for_saving}') with subreddits: {clean_subreddits}")
                
            except Exception as e:
                print(f"[ERROR] Error processing subreddits for category {user_category.category_name}: {e}")
                continue
    
    db.close()
    return {"status": "scheduled", "user_id": user_id, "categories_processed": len(user_categories)}

@celery_app.task(bind=True)
def ingest_reddit_for_all_users(self):
    """Trigger Reddit ingestion for all users with categories"""
    from shared.models.database_models import UserCategory
    import json
    
    db = SessionLocal()
    
    # Get all users with categories
    user_categories = db.query(UserCategory).filter(
        UserCategory.is_active == True
    ).all()
    
    if not user_categories:
        db.close()
        return {"status": "no_users_with_categories"}
    
    # Group categories by user
    users_with_categories = {}
    for user_cat in user_categories:
        if user_cat.user_id not in users_with_categories:
            users_with_categories[user_cat.user_id] = []
        users_with_categories[user_cat.user_id].append(user_cat)
    
    total_scheduled = 0
    users_processed = 0
    
    try:
        for user_id, categories in users_with_categories.items():
            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "current_user": user_id,
                    "processed": users_processed + 1,
                    "total": len(users_with_categories)
                }
            )
            
            for user_category in categories:
                if user_category.subreddits:
                    try:
                        subreddits = json.loads(user_category.subreddits)
                        # Remove 'r/' prefix if present and deduplicate
                        clean_subreddits = list(set([sub.replace('r/', '') for sub in subreddits]))
                        
                        # Use short_summary for category if available, otherwise fallback to category_name
                        category_for_saving = user_category.short_summary if user_category.short_summary else user_category.category_name
                        
                        # Schedule Reddit ingestion for this category
                        ingest_reddit_with_category.apply_async(args=[clean_subreddits, category_for_saving])
                        total_scheduled += 1
                        print(f"[DEBUG] Scheduled Reddit ingestion for user {user_id}, category '{user_category.category_name}' (saving as '{category_for_saving}') with subreddits: {clean_subreddits}")
                        
                    except Exception as e:
                        print(f"[ERROR] Error processing subreddits for category {user_category.category_name}: {e}")
                        continue
            
            users_processed += 1
        
        return {
            "status": "completed",
            "scheduled": total_scheduled,
            "users_processed": users_processed,
            "total_users": len(users_with_categories)
        }
        
    except Exception as e:
        print(f"[ERROR] Reddit all users ingestion failed: {e}")
        raise self.retry(countdown=60, max_retries=3)
    
    finally:
        db.close()

if __name__ == "__main__":
    # Test the runner
    runner = RedditRunner()
    # The authenticate method is removed, so this test will fail.
    # If you want to test the new methods, you'd need to mock authentication or
    # adjust the test to call get_subreddit_posts_with_comments directly.
    # For now, keeping the original test structure.
    # posts = runner.get_subreddit_posts_with_comments("technology", limit=5)
    # print(json.dumps(posts, indent=2))
    pass # Removed the test call as authenticate is removed

# Add FastAPI debug endpoint if this file is run as main or imported in a FastAPI app
try:
    from fastapi import APIRouter
    router = APIRouter()
    @router.get("/debug/reddit-history")
    async def get_reddit_history():
        db = SessionLocal()
        try:
            records = db.query(RedditCallHistory).order_by(RedditCallHistory.timestamp.desc()).limit(100).all()
            return [
                {
                    'timestamp': r.timestamp.isoformat() + 'Z',
                    'subreddit': r.subreddit,
                    'url': r.url,
                    'response_status_code': r.response_status_code,
                    'posts_found': r.posts_found,
                    'posts_saved': r.posts_saved,
                    'error_message': r.error_message,
                    'response_content': r.response_content
                }
                for r in records
            ]
        finally:
            db.close()
except ImportError:
    pass 