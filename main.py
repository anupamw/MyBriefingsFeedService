from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import sqlite3
from datetime import datetime
import os

app = FastAPI(
    title="My Briefings Feed Service",
    description="A FastAPI service for serving personalized news feeds",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = "/app/data/feed.db"

def init_db():
    """Initialize the database with tables and sample data"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Create feed_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feed_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            content TEXT,
            url TEXT,
            source TEXT,
            published_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample data if table is empty
    cursor.execute("SELECT COUNT(*) FROM feed_items")
    if cursor.fetchone()[0] == 0:
        sample_items = [
            ("Breaking: AI Breakthrough", "Scientists discover new AI algorithm", "Full article content here...", "https://example.com/ai-news", "Tech News", "2024-01-15T10:00:00Z"),
            ("Market Update", "Stock market reaches new highs", "Market analysis and insights...", "https://example.com/market", "Finance Daily", "2024-01-15T09:30:00Z"),
            ("Sports Highlights", "Championship game results", "Complete game coverage...", "https://example.com/sports", "Sports Central", "2024-01-15T08:45:00Z"),
            ("Health & Wellness", "New study on nutrition", "Research findings and recommendations...", "https://example.com/health", "Health Weekly", "2024-01-15T07:15:00Z"),
            ("Entertainment News", "Award show winners announced", "Complete list of winners...", "https://example.com/entertainment", "Entertainment Now", "2024-01-15T06:00:00Z"),
        ]
        
        cursor.executemany('''
            INSERT INTO feed_items (title, summary, content, url, source, published_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_items)
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Pydantic models
class Item(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float

class FeedItem(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    created_at: Optional[str] = None

# In-memory storage (replace with database in production)
items_db = []
item_id_counter = 1

@app.get("/")
async def root():
    return {"message": "Welcome to my such an amazing fantastical FastAPI Web App!", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "My Briefings Feed Service"}

@app.get("/feed", response_model=List[FeedItem])
async def get_feed(limit: int = 10, offset: int = 0):
    """Get feed items with pagination"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, summary, content, url, source, published_at, created_at
        FROM feed_items
        ORDER BY published_at DESC, created_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    items = []
    for row in cursor.fetchall():
        items.append(FeedItem(
            id=row[0],
            title=row[1],
            summary=row[2],
            content=row[3],
            url=row[4],
            source=row[5],
            published_at=row[6],
            created_at=row[7]
        ))
    
    conn.close()
    return items

@app.get("/feed/{item_id}", response_model=FeedItem)
async def get_feed_item(item_id: int):
    """Get a specific feed item by ID"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, summary, content, url, source, published_at, created_at
        FROM feed_items
        WHERE id = ?
    ''', (item_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Feed item not found")
    
    return FeedItem(
        id=row[0],
        title=row[1],
        summary=row[2],
        content=row[3],
        url=row[4],
        source=row[5],
        published_at=row[6],
        created_at=row[7]
    )

@app.get("/items", response_model=List[Item])
async def get_items():
    return items_db

@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    for item in items_db:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/items", response_model=Item)
async def create_item(item: Item):
    global item_id_counter
    item.id = item_id_counter
    item_id_counter += 1
    items_db.append(item)
    return item

@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item: Item):
    for i, existing_item in enumerate(items_db):
        if existing_item.id == item_id:
            item.id = item_id
            items_db[i] = item
            return item
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    for i, item in enumerate(items_db):
        if item.id == item_id:
            del items_db[i]
            return {"message": "Item deleted successfully"}
    raise HTTPException(status_code=404, detail="Item not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 