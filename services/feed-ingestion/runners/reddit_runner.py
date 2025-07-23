import os
import requests
import json
import time
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from dotenv import load_dotenv

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from shared.database.connection import SessionLocal
from shared.models.database_models import DataSource, FeedItem, IngestionJob
from celery_app import celery_app

load_dotenv()

class RedditRunner:
    """Runner for Reddit API integration"""
    def __init__(self):
        self.user_agent = "python:MyBriefingsFeedService:v1.0"
        self.base_url = "https://www.reddit.com"
        self.db = SessionLocal()

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
        # Try RSS feed first (more reliable than JSON API)
        rss_url = f'{self.base_url}/r/{subreddit}/.rss'
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        print(f"[DEBUG] Fetching Reddit RSS from: {rss_url}")
        resp = requests.get(rss_url, headers=headers)
        print(f"[DEBUG] Reddit RSS response status: {resp.status_code}")
        
        if resp.status_code == 200:
            # Parse RSS feed
            import feedparser
            feed = feedparser.parse(resp.text)
            posts = []
            print(f"[DEBUG] Found {len(feed.entries)} entries in RSS feed")
            
            for entry in feed.entries[:limit]:
                # Extract publication date
                published = datetime.utcnow()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                
                posts.append({
                    'title': entry.get('title', ''),
                    'summary': entry.get('summary', ''),
                    'score': 0,  # RSS doesn't provide scores
                    'url': entry.get('link', ''),
                    'subreddit': subreddit,
                    'created_utc': published.timestamp(),
                    'top_comment': None  # RSS doesn't provide comments
                })
            return posts
        else:
            print(f"[DEBUG] RSS failed, trying JSON API as fallback")
            # Fallback to JSON API
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
            if resp.status_code != 200:
                print(f"[DEBUG] Reddit API error: {resp.text[:200]}")
                return []
            data = resp.json()
            posts = []
            if 'data' in data and 'children' in data['data']:
                print(f"[DEBUG] Found {len(data['data']['children'])} posts in response")
                for post in data['data']['children']:
                    post_data = post['data']
                    post_id = post_data['id']
                    top_comment = self.get_top_comment(subreddit, post_id)
                    posts.append({
                        'title': post_data.get('title', ''),
                        'summary': post_data.get('selftext', ''),
                        'score': post_data.get('score', 0),
                        'url': f"https://reddit.com{post_data.get('permalink', '')}",
                        'subreddit': subreddit,
                        'created_utc': post_data.get('created_utc', 0),
                        'top_comment': top_comment
                    })
            else:
                print(f"[DEBUG] No posts found in Reddit response")
            return posts

    def save_feed_items_with_comments(self, posts: list, data_source):
        created = 0
        for post in posts:
            try:
                # Truncate title to fit database field
                title = post.get("title", "Untitled")
                if len(title) > 500:
                    title = title[:497] + "..."
                
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
                    category=post.get('subreddit', 'Reddit'),
                    tags=["reddit", post.get("subreddit", "").lower()]
                )
                print(f"[DEBUG] Saving Reddit post: '{feed_item.title}' with category '{feed_item.category}'")
                self.db.add(feed_item)
                created += 1
            except Exception as e:
                print(f"Error saving Reddit post: {e}")
                continue
        self.db.commit()
        print(f"[DEBUG] Successfully saved {created} Reddit posts to database")
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
def ingest_reddit_for_user(self, user_id: int):
    """Trigger Reddit ingestion for a specific user based on their categories"""
    from shared.models.database_models import UserCategory
    import json
    db = SessionLocal()
    user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
    subreddits = []
    for cat in user_categories:
        if cat.subreddits:
            try:
                subreddits.extend(json.loads(cat.subreddits))
            except Exception:
                continue
    if subreddits:
        # Remove 'r/' prefix if present and deduplicate
        clean_subreddits = list(set([sub.replace('r/', '') for sub in subreddits]))
        ingest_reddit.apply_async(args=[clean_subreddits])
        db.close()
        return {"status": "scheduled", "user_id": user_id, "subreddits": clean_subreddits}
    else:
        db.close()
        return {"status": "no_subreddits", "user_id": user_id}

@celery_app.task(bind=True)
def ingest_reddit_for_all_users(self):
    from shared.models.database_models import UserCategory, UserDB
    import json
    db = SessionLocal()
    user_ids = [u.id for u in db.query(UserDB.id).all()]
    for user_id in user_ids:
        user_categories = db.query(UserCategory).filter(UserCategory.user_id == user_id).all()
        subreddits = []
        for cat in user_categories:
            if cat.subreddits:
                try:
                    subreddits.extend(json.loads(cat.subreddits))
                except Exception:
                    continue
        if subreddits:
            ingest_reddit.apply_async(args=[list(set(subreddits))])
    db.close()
    return {"status": "scheduled"}

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