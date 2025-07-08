import os
import requests
import json
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task
from dotenv import load_dotenv

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
from shared.database.connection import SessionLocal
from shared.models.database_models import DataSource, FeedItem, IngestionJob, ContentCache
from celery_app import celery_app

load_dotenv()

class SocialRunner:
    """Runner for various social media sources"""
    
    def __init__(self):
        self.db = SessionLocal()
        
    def get_data_source(self) -> Optional[DataSource]:
        """Get social data source configuration"""
        return self.db.query(DataSource).filter(
            DataSource.name == "social",
            DataSource.is_active == True
        ).first()
    
    def get_rss_feeds(self) -> List[Dict]:
        """Get list of RSS feeds to monitor"""
        return [
            {
                "name": "TechCrunch",
                "url": "https://techcrunch.com/feed/",
                "category": "Technology"
            },
            {
                "name": "Ars Technica",
                "url": "https://feeds.arstechnica.com/arstechnica/index",
                "category": "Technology"
            },
            {
                "name": "BBC News",
                "url": "https://feeds.bbci.co.uk/news/rss.xml",
                "category": "News"
            },
            {
                "name": "Hacker News",
                "url": "https://news.ycombinator.com/rss",
                "category": "Technology"
            },
            {
                "name": "The Verge",
                "url": "https://www.theverge.com/rss/index.xml",
                "category": "Technology"
            }
        ]
    
    def parse_rss_feed(self, feed_url: str, feed_name: str, category: str) -> List[Dict]:
        """Parse RSS feed and extract articles"""
        try:
            feed = feedparser.parse(feed_url)
            articles = []
            
            for entry in feed.entries[:20]:  # Limit to 20 articles
                # Extract publication date
                published = datetime.utcnow()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                
                # Extract content
                content = ""
                if hasattr(entry, 'summary'):
                    content = entry.summary
                elif hasattr(entry, 'content') and entry.content:
                    content = entry.content[0].value
                
                articles.append({
                    "title": entry.title,
                    "content": content,
                    "url": entry.link,
                    "published_at": published,
                    "source": feed_name,
                    "category": category,
                    "author": getattr(entry, 'author', 'Unknown'),
                    "tags": getattr(entry, 'tags', [])
                })
            
            return articles
            
        except Exception as e:
            print(f"Error parsing RSS feed {feed_url}: {e}")
            return []
    
    def get_mastodon_posts(self, instance: str, hashtag: str = None, limit: int = 20) -> List[Dict]:
        """Get posts from Mastodon instance"""
        try:
            # Mastodon public timeline API
            if hashtag:
                url = f"https://{instance}/api/v1/timelines/tag/{hashtag}"
            else:
                url = f"https://{instance}/api/v1/timelines/public"
            
            headers = {
                "User-Agent": "MyBriefingsFeedService/1.0"
            }
            
            params = {
                "limit": limit
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            posts = response.json()
            processed_posts = []
            
            for post in posts:
                # Filter out low-quality posts
                if len(post.get("content", "")) < 50:
                    continue
                
                # Parse content (remove HTML tags)
                import re
                content = re.sub(r'<[^>]+>', '', post.get("content", ""))
                
                processed_posts.append({
                    "title": f"Post by {post.get('account', {}).get('display_name', 'Unknown')}",
                    "content": content,
                    "url": post.get("url", ""),
                    "published_at": datetime.fromisoformat(post.get("created_at").replace("Z", "+00:00")),
                    "source": f"Mastodon ({instance})",
                    "category": "Social Media",
                    "author": post.get("account", {}).get("display_name", "Unknown"),
                    "engagement_score": post.get("reblogs_count", 0) + post.get("favourites_count", 0)
                })
            
            return processed_posts
            
        except Exception as e:
            print(f"Error fetching Mastodon posts from {instance}: {e}")
            return []
    
    def get_github_trending(self, language: str = None, since: str = "daily") -> List[Dict]:
        """Get trending repositories from GitHub"""
        try:
            # Note: GitHub doesn't have a public API for trending, so we'll use a proxy
            # In a real implementation, you might want to scrape the trending page
            # or use a service like GitHub Trending API
            
            url = "https://github-trending-api.now.sh/repositories"
            params = {
                "language": language or "all",
                "since": since
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            repos = response.json()
            processed_repos = []
            
            for repo in repos[:10]:  # Limit to 10 repos
                processed_repos.append({
                    "title": f"{repo.get('name', 'Unknown')} - {repo.get('description', 'No description')}",
                    "content": f"Repository: {repo.get('name', 'Unknown')}\nStars: {repo.get('stars', 0)}\nLanguage: {repo.get('language', 'Unknown')}",
                    "url": repo.get("url", ""),
                    "published_at": datetime.utcnow(),
                    "source": "GitHub Trending",
                    "category": "Technology",
                    "author": repo.get("author", "Unknown"),
                    "engagement_score": repo.get("stars", 0)
                })
            
            return processed_repos
            
        except Exception as e:
            print(f"Error fetching GitHub trending: {e}")
            return []
    
    def save_feed_items(self, items: List[Dict], data_source: DataSource) -> Dict[str, int]:
        """Save social media items as feed items"""
        created = 0
        updated = 0
        
        # Delete older items from the same source to prevent storage bloat
        if items:
            try:
                # Delete items older than 7 days from the same source
                cutoff_date = datetime.utcnow() - timedelta(days=7)
                deleted_count = self.db.query(FeedItem).filter(
                    FeedItem.data_source_id == data_source.id,
                    FeedItem.created_at < cutoff_date
                ).delete()
                print(f"Deleted {deleted_count} old items from {data_source.name}")
            except Exception as e:
                print(f"Error deleting old items: {e}")
        
        for item in items:
            try:
                # Check if item already exists (by URL)
                existing_item = self.db.query(FeedItem).filter(
                    FeedItem.url == item.get("url"),
                    FeedItem.data_source_id == data_source.id
                ).first()
                
                if existing_item:
                    # Update existing item
                    existing_item.title = item.get("title", existing_item.title)
                    existing_item.content = item.get("content", existing_item.content)
                    existing_item.engagement_score = item.get("engagement_score", existing_item.engagement_score)
                    existing_item.updated_at = datetime.utcnow()
                    existing_item.raw_data = item
                    updated += 1
                else:
                    # Create new item
                    feed_item = FeedItem(
                        title=item.get("title", "Untitled"),
                        content=item.get("content", ""),
                        url=item.get("url", ""),
                        source=item.get("source", "Social Media"),
                        data_source_id=data_source.id,
                        published_at=item.get("published_at", datetime.utcnow()),
                        engagement_score=item.get("engagement_score", 0),
                        raw_data=item,
                        category=item.get("category", "Social Media"),
                        tags=[item.get("category", "").lower()]
                    )
                    self.db.add(feed_item)
                    created += 1
                
            except Exception as e:
                print(f"Error saving social media item: {e}")
                continue
        
        self.db.commit()
        return {"created": created, "updated": updated}

@celery_app.task(bind=True)
def ingest_social(self, sources: List[str] = None):
    """Celery task for social media ingestion"""
    runner = SocialRunner()
    data_source = runner.get_data_source()
    
    if not data_source:
        print("Social data source not found or inactive")
        return {"error": "Data source not found"}
    
    if sources is None:
        sources = ["rss", "mastodon", "github"]
    
    # Create ingestion job record
    job = IngestionJob(
        job_type="social",
        status="running",
        started_at=datetime.utcnow(),
        parameters={"sources": sources},
        data_source_id=data_source.id
    )
    runner.db.add(job)
    runner.db.commit()
    
    total_created = 0
    total_updated = 0
    
    try:
        # Process RSS feeds
        if "rss" in sources:
            self.update_state(state="PROGRESS", meta={"current_source": "RSS feeds"})
            rss_feeds = runner.get_rss_feeds()
            
            for feed in rss_feeds:
                articles = runner.parse_rss_feed(feed["url"], feed["name"], feed["category"])
                if articles:
                    results = runner.save_feed_items(articles, data_source)
                    total_created += results["created"]
                    total_updated += results["updated"]
        
        # Process Mastodon posts
        if "mastodon" in sources:
            self.update_state(state="PROGRESS", meta={"current_source": "Mastodon"})
            mastodon_instances = ["mastodon.social", "tech.lgbt"]
            
            for instance in mastodon_instances:
                posts = runner.get_mastodon_posts(instance)
                if posts:
                    results = runner.save_feed_items(posts, data_source)
                    total_created += results["created"]
                    total_updated += results["updated"]
        
        # Process GitHub trending
        if "github" in sources:
            self.update_state(state="PROGRESS", meta={"current_source": "GitHub"})
            repos = runner.get_github_trending()
            if repos:
                results = runner.save_feed_items(repos, data_source)
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
            "sources_processed": len(sources)
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
    runner = SocialRunner()
    rss_feeds = runner.get_rss_feeds()
    if rss_feeds:
        articles = runner.parse_rss_feed(rss_feeds[0]["url"], rss_feeds[0]["name"], rss_feeds[0]["category"])
        print(json.dumps(articles[:2], indent=2)) 