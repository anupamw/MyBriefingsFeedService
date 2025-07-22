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
from shared.models.database_models import DataSource, FeedItem, IngestionJob
from celery_app import celery_app

load_dotenv()

class RedditRunner:
    """Runner for Reddit API integration"""
    def __init__(self):
        self.user_agent = "MyBriefingsFeedService/1.0"
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
        url = f'{self.base_url}/r/{subreddit}/top.json?limit={limit}&t={time_filter}'
        headers = {'User-Agent': self.user_agent}
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return []
        data = resp.json()
        posts = []
        if 'data' in data and 'children' in data['data']:
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
        return posts

    def save_feed_items_with_comments(self, posts: list, data_source):
        created = 0
        for post in posts:
            try:
                feed_item = FeedItem(
                    title=post.get("title", "Untitled"),
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
                self.db.add(feed_item)
                created += 1
            except Exception as e:
                print(f"Error saving Reddit post: {e}")
                continue
        self.db.commit()
        return {"created": created}

@celery_app.task(bind=True)
def ingest_reddit(self, subreddits: list = None, time_filter: str = "day"):
    runner = RedditRunner()
    data_source = runner.db.query(DataSource).filter(DataSource.name == "reddit").first()
    if not data_source:
        print("Reddit data source not found or inactive")
        return {"error": "Data source not found"}
    
    # Handle None subreddits
    if subreddits is None:
        subreddits = []
    
    total_created = 0
    for subreddit in subreddits:
        posts = runner.get_subreddit_posts_with_comments(subreddit, limit=3, time_filter=time_filter)
        if posts:
            results = runner.save_feed_items_with_comments(posts, data_source)
            total_created += results["created"]
    runner.db.close()
    return {"status": "completed", "created": total_created, "subreddits_processed": len(subreddits)}

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