import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add the services directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.database.connection import get_db
from shared.models.database_models import FeedItem, DataSource
from celery_app import celery_app


class CleanupRunner:
    """Handles automated cleanup of old feed items"""
    
    def __init__(self):
        self.db = get_db()
    
    def cleanup_old_feed_items(self, hours_old: int = 24) -> Dict[str, int]:
        """Delete feed items older than specified hours"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(hours=hours_old)
            
            # Count old items before deletion
            old_count = self.db.query(FeedItem).filter(
                FeedItem.created_at < cutoff_date
            ).count()
            
            # Delete old feed items
            deleted_count = self.db.query(FeedItem).filter(
                FeedItem.created_at < cutoff_date
            ).delete()
            
            self.db.commit()
            
            print(f"[CLEANUP] Deleted {deleted_count} feed items older than {hours_old} hours")
            
            return {
                "deleted_count": deleted_count,
                "total_old_items_found": old_count,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"[ERROR] Cleanup old feed items error: {e}")
            raise
    
    def cleanup_source_items_for_user(self, user_id: int, source_name: str) -> Dict[str, int]:
        """Clean up all feed items from a specific source for a specific user before inserting new ones"""
        try:
            # Get user's categories
            from shared.models.database_models import UserCategory
            user_categories = self.db.query(UserCategory).filter(
                UserCategory.user_id == user_id
            ).all()
            
            if not user_categories:
                return {"deleted_count": 0, "message": "No categories found for user"}
            
            # Get category names for this user
            category_names = [cat.category_name for cat in user_categories]
            
            # Count items to be deleted
            items_to_delete = self.db.query(FeedItem).filter(
                FeedItem.category.in_(category_names),
                FeedItem.source.like(f"%{source_name}%")
            ).count()
            
            # Delete all feed items from this source for this user's categories
            deleted_count = self.db.query(FeedItem).filter(
                FeedItem.category.in_(category_names),
                FeedItem.source.like(f"%{source_name}%")
            ).delete()
            
            self.db.commit()
            
            if deleted_count > 0:
                print(f"[CLEANUP] Deleted {deleted_count} old {source_name} items for user {user_id}")
            
            return {
                "deleted_count": deleted_count,
                "items_found": items_to_delete,
                "source": source_name,
                "user_id": user_id
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"[ERROR] Cleanup source items for user error: {e}")
            raise
    
    def cleanup_source_items_by_category(self, category_name: str, source_name: str) -> Dict[str, int]:
        """Clean up all feed items from a specific source for a specific category"""
        try:
            # Count items to be deleted
            items_to_delete = self.db.query(FeedItem).filter(
                FeedItem.category == category_name,
                FeedItem.source.like(f"%{source_name}%")
            ).count()
            
            # Delete all feed items from this source for this category
            deleted_count = self.db.query(FeedItem).filter(
                FeedItem.category == category_name,
                FeedItem.source.like(f"%{source_name}%")
            ).delete()
            
            self.db.commit()
            
            if deleted_count > 0:
                print(f"[CLEANUP] Deleted {deleted_count} old {source_name} items for category '{category_name}'")
            
            return {
                "deleted_count": deleted_count,
                "items_found": items_to_delete,
                "source": source_name,
                "category": category_name
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"[ERROR] Cleanup source items by category error: {e}")
            raise


@celery_app.task(bind=True)
def cleanup_old_feed_items(self, hours_old: int = 24):
    """Celery task for cleaning up old feed items"""
    try:
        runner = CleanupRunner()
        result = runner.cleanup_old_feed_items(hours_old)
        
        print(f"[CLEANUP TASK] Completed: {result}")
        return result
        
    except Exception as e:
        print(f"[ERROR] Cleanup task failed: {e}")
        raise


@celery_app.task(bind=True)
def cleanup_source_items_for_user(self, user_id: int, source_name: str):
    """Celery task for cleaning up source items for a specific user"""
    try:
        runner = CleanupRunner()
        result = runner.cleanup_source_items_for_user(user_id, source_name)
        
        print(f"[CLEANUP TASK] User cleanup completed: {result}")
        return result
        
    except Exception as e:
        print(f"[ERROR] User cleanup task failed: {e}")
        raise


@celery_app.task(bind=True)
def cleanup_source_items_by_category(self, category_name: str, source_name: str):
    """Celery task for cleaning up source items for a specific category"""
    try:
        runner = CleanupRunner()
        result = runner.cleanup_source_items_by_category(category_name, source_name)
        
        print(f"[CLEANUP TASK] Category cleanup completed: {result}")
        return result
        
    except Exception as e:
        print(f"[ERROR] Category cleanup task failed: {e}")
        raise 