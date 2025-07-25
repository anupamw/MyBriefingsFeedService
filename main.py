from fastapi import FastAPI, HTTPException, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import time

# Load environment variables from .env file
load_dotenv()

# Configuration
INGESTION_SERVICE_URL = os.getenv("INGESTION_SERVICE_URL", "http://my-briefings-ingestion-service:8001")

app = FastAPI(
    title="My Briefings Feed Service",
    description="A FastAPI service for serving personalized news feeds",
    version="1.0.0"
)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token security
security = HTTPBearer()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fastapi:password@localhost:5432/briefings_feed")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class UserDB(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FeedItemDB(Base):
    __tablename__ = "feed_items"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    content = Column(Text)
    url = Column(String(1000))
    source = Column(String(100))
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    category = Column(String(100))  # Add category field

class UserCategoryDB(Base):
    __tablename__ = "user_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    category_name = Column(String(140), nullable=False)  # Limited to 140 characters
    short_summary = Column(String(50), nullable=True)  # Up to 4-word summary for display
    subreddits = Column(Text, nullable=True)  # JSON string
    twitter = Column(Text, nullable=True)     # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        # Ensure unique combination of user_id and category_name
        UniqueConstraint('user_id', 'category_name', name='unique_user_category'),
    )

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize the database with sample data"""
    db = SessionLocal()
    
    # Check if feed_items table is empty
    feed_count = db.query(FeedItemDB).count()
    
    if feed_count == 0:
        sample_items = [
            FeedItemDB(
                title="Breaking: AI Breakthrough",
                summary="Scientists discover new AI algorithm",
                content="Full article content here...",
                url="https://example.com/ai-news",
                source="Tech News",
                published_at=datetime.fromisoformat("2024-01-15T10:00:00Z")
            ),
            FeedItemDB(
                title="Market Update",
                summary="Stock market reaches new highs",
                content="Market analysis and insights...",
                url="https://example.com/market",
                source="Finance Daily",
                published_at=datetime.fromisoformat("2024-01-15T09:30:00Z")
            ),
            FeedItemDB(
                title="Sports Highlights",
                summary="Championship game results",
                content="Complete game coverage...",
                url="https://example.com/sports",
                source="Sports Central",
                published_at=datetime.fromisoformat("2024-01-15T08:45:00Z")
            ),
            FeedItemDB(
                title="Health & Wellness",
                summary="New study on nutrition",
                content="Research findings and recommendations...",
                url="https://example.com/health",
                source="Health Weekly",
                published_at=datetime.fromisoformat("2024-01-15T07:15:00Z")
            ),
            FeedItemDB(
                title="Entertainment News",
                summary="Award show winners announced",
                content="Complete list of winners...",
                url="https://example.com/entertainment",
                source="Entertainment Now",
                published_at=datetime.fromisoformat("2024-01-15T06:00:00Z")
            ),
        ]
        
        db.add_all(sample_items)
        db.commit()
    
    db.close()

# Initialize database on startup
init_db()

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class User(BaseModel):
    id: int
    username: str
    email: str
    created_at: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class Item(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float

class FeedItem(BaseModel):
    id: int
    summary: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    category: Optional[str] = None
    short_summary: Optional[str] = None

class UserCategory(BaseModel):
    id: int
    user_id: int
    category_name: str
    short_summary: Optional[str] = None
    subreddits: Optional[str] = None
    twitter: Optional[str] = None
    created_at: Optional[str] = None

class UserCategoryCreate(BaseModel):
    category_name: str

# Authentication functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_by_username(username: str):
    db = SessionLocal()
    user = db.query(UserDB).filter(UserDB.username == username).first()
    db.close()
    if user:
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "hashed_password": user.hashed_password,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    return None

def authenticate_user(username: str, password: str):
    user = get_user_by_username(username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return user

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = get_user_by_username(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# Legacy in-memory storage for demo items (legacy endpoints only)
# Note: Users and feed data are stored in SQLite database
items_db = []
item_id_counter = 1

# Helper function for UTC ISO string with 'Z'
def to_utc_z(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace('+00:00', 'Z')

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application page"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <title>My Briefings Feed Service</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f8f9fa;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                padding: 40px;
                width: 100%;
                max-width: 400px;
                text-align: center;
                border: 1px solid #e9ecef;
            }
            
            .logo {
                font-size: 2.5em;
                font-weight: bold;
                color: #6c757d;
                margin-bottom: 10px;
            }
            
            .subtitle {
                color: #666;
                margin-bottom: 30px;
            }
            
            .form-container {
                display: none;
            }
            
            .form-container.active {
                display: block;
            }
            
            .form-group {
                margin-bottom: 20px;
                text-align: left;
            }
            
            label {
                display: block;
                margin-bottom: 5px;
                color: #333;
                font-weight: 500;
            }
            
            input {
                width: 100%;
                padding: 12px;
                border: 2px solid #e1e5e9;
                border-radius: 10px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            
            input:focus {
                outline: none;
                border-color: #a8d5ba;
            }
            
            button {
                width: 100%;
                padding: 12px;
                background: #a8d5ba;
                color: #2c3e50;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            button:hover {
                background: #95c9a8;
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            
            .toggle-form {
                margin-top: 20px;
                color: #a8d5ba;
                cursor: pointer;
                text-decoration: underline;
            }
            
            .feed-container {
                display: none;
                max-width: 1200px;
                width: 100%;
            }
            
            .main-content {
                display: flex;
                gap: 30px;
                margin-top: 20px;
            }
            
            .sidebar {
                background: white;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                width: 300px;
                flex-shrink: 0;
            }
            
            .sidebar h3 {
                margin-bottom: 20px;
                color: #333;
                font-size: 1.2em;
            }
            
            .category-item {
                background: white;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                transition: all 0.2s;
            }
            
            .category-item:hover {
                border-color: #a8d5ba;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            
            .category-name {
                font-weight: 500;
                color: #333;
            }
            
            .delete-category {
                background: #f8d7da;
                color: #721c24;
                border: none;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                cursor: pointer;
                transition: all 0.2s;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                min-width: 20px;
                flex-shrink: 0;
            }
            
            .delete-category:hover {
                background: #f5c6cb;
            }
            
            .add-category {
                margin-top: 20px;
            }
            
            .add-category input {
                width: 100%;
                padding: 8px;
                border: 2px solid #e1e5e9;
                border-radius: 6px;
                margin-bottom: 10px;
                font-size: 14px;
            }
            
            .add-category button {
                width: 100%;
                padding: 8px;
                background: #a8d5ba;
                color: #2c3e50;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .add-category button:hover {
                background: #95c9a8;
            }
            
            .feed-content {
                flex: 1;
            }
            
            .feed-header {
                background: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                border: 1px solid #e9ecef;
            }
            
            .feed-item {
                background: white;
                border-radius: 20px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                border: 1px solid #e9ecef;
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .feed-item:hover {
                transform: translateY(-3px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.12);
                border-color: #a8d5ba;
            }
            
            .feed-item::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(90deg, #a8d5ba, #95c9a8);
                border-radius: 20px 20px 0 0;
            }
            
            .feed-title {
                font-size: 1.3em;
                font-weight: 600;
                color: #333;
                margin-bottom: 10px;
            }
            
            .feed-summary {
                color: #666;
                margin-bottom: 10px;
                line-height: 1.5;
            }
            
            .feed-meta {
                display: flex;
                justify-content: space-between;
                color: #999;
                font-size: 0.9em;
            }
            
            .logout-btn {
                background: #f8d7da;
                color: #721c24;
                margin-top: 20px;
                padding: 6px 16px;
                font-size: 0.95em;
                width: auto;
                min-width: 0;
                border-radius: 6px;
            }
            
            .logout-btn:hover {
                background: #f5c6cb;
            }
            
            .error {
                color: #721c24;
                margin-top: 10px;
                font-size: 0.9em;
            }
            
            .success {
                color: #155724;
                margin-top: 10px;
                font-size: 0.9em;
            }
            .feed-card-text {
                color: #333;
                font-size: 1.05em;
                line-height: 1.5;
                margin-bottom: 8px;
                display: -webkit-box;
                -webkit-line-clamp: 5;
                -webkit-box-orient: vertical;
                overflow: hidden;
                text-overflow: ellipsis;
                transition: max-height 0.3s;
            }
            .feed-card-text.expanded {
                -webkit-line-clamp: unset;
                max-height: 1000em;
                overflow: visible;
            }
            .feed-card-more {
                color: #a8d5ba;
                cursor: pointer;
                font-size: 0.95em;
                font-weight: 500;
                margin-bottom: 8px;
                display: inline-block;
            }
            .reddit-card {
                background: #fff;
                border: 1.5px solid #ff4500;
                border-radius: 16px;
                padding: 22px 22px 16px 22px;
                margin-bottom: 18px;
                box-shadow: 0 2px 8px rgba(255,69,0,0.08);
                transition: box-shadow 0.2s;
            }
            .reddit-card:hover {
                box-shadow: 0 6px 24px rgba(255,69,0,0.13);
                border-color: #ff6a1a;
            }
            .reddit-card .reddit-title {
                font-size: 1.15em;
                font-weight: 700;
                color: #ff4500;
                margin-bottom: 8px;
            }
            .reddit-card .reddit-top-comment {
                color: #333;
                font-size: 1em;
                margin-bottom: 10px;
            }
            .reddit-card .reddit-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 0.95em;
                color: #888;
                margin-top: 8px;
            }
            .reddit-card a {
                color: #ff4500;
                text-decoration: none;
                font-weight: 500;
            }
            .reddit-card a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container" id="auth-container">
            <div class="logo">📰</div>
            <div class="subtitle">My Briefings Feed Service</div>
            
            <!-- Login Form -->
            <div class="form-container active" id="login-form">
                <h2>Sign In</h2>
                <div class="form-group">
                    <label for="login-username">Username</label>
                    <input type="text" id="login-username" placeholder="Enter your username">
                </div>
                <div class="form-group">
                    <label for="login-password">Password</label>
                    <input type="password" id="login-password" placeholder="Enter your password">
                </div>
                <button onclick="login()">Sign In</button>
                <div class="toggle-form" onclick="toggleForm('signup')">Don't have an account? Sign up</div>
            </div>
            
            <!-- Signup Form -->
            <div class="form-container" id="signup-form">
                <h2>Sign Up</h2>
                <div class="form-group">
                    <label for="signup-username">Username</label>
                    <input type="text" id="signup-username" placeholder="Choose a username">
                </div>
                <div class="form-group">
                    <label for="signup-email">Email</label>
                    <input type="email" id="signup-email" placeholder="Enter your email">
                </div>
                <div class="form-group">
                    <label for="signup-password">Password</label>
                    <input type="password" id="signup-password" placeholder="Choose a password">
                </div>
                <button onclick="signup()">Sign Up</button>
                <div class="toggle-form" onclick="toggleForm('login')">Already have an account? Sign in</div>
            </div>
        </div>
        
        <div class="feed-container" id="feed-container">
            <div class="feed-header">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <div>
                        <h1 id="feed-header-title">Welcome to Your Feed! 📰</h1>
                        <p>Here are your personalized news briefings</p>
                    </div>
                    <div id="digital-clock" style="background: #f8f9fa; color: #495057; padding: 7px 16px; border-radius: 8px; font-family: 'Fira Mono', 'Consolas', 'Menlo', monospace; font-size: 1.05em; font-weight: 500; letter-spacing: 0.01em; box-shadow: 0 1px 4px rgba(40,60,80,0.06); border: 1px solid #dee2e6; display: inline-block; margin-left: 10px;">
                    </div>
                </div>
                <button class="logout-btn" onclick="logout()">Logout</button>
            </div>
            
            <div class="main-content">
                <div class="sidebar">
                    <h3>Your Categories</h3>
                    <div style="margin-bottom: 15px;">
                        <span style="cursor: pointer; color: #a8d5ba; text-decoration: underline; font-weight: 500;" onclick="clearCategoryFilter()">Show All</span>
                    </div>
                    <div id="categories-list"></div>
                    <div class="add-category">
                        <input type="text" id="new-category" placeholder="Enter category name (max 140 chars)" maxlength="140">
                        <button onclick="addCategory()">Add Category</button>
                    </div>
                </div>
                
                <div class="feed-content">
                    <div id="feed-items"></div>
                    <div id="pagination-controls" style="display:flex;justify-content:center;gap:10px;margin-top:20px;"></div>
                </div>
            </div>
        </div>
        
        <script>
            // Version: 2025-07-22-01 - Force cache refresh
            // Escape HTML to prevent XSS
            function escapeHtml(text) {
                if (!text) return '';
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            

            
            let feedRefreshInterval = null;

            function startPeriodicFeedRefresh() {
                if (feedRefreshInterval) clearInterval(feedRefreshInterval);
                feedRefreshInterval = setInterval(() => {
                    // Only refresh if user is still logged in
                    const token = localStorage.getItem('token');
                    if (token) {
                        showFeed(currentOffset, currentCategoryFilter);
                    } else {
                        clearInterval(feedRefreshInterval);
                    }
                }, 60000); // 1 minute
            }

            function stopPeriodicFeedRefresh() {
                if (feedRefreshInterval) {
                    clearInterval(feedRefreshInterval);
                    feedRefreshInterval = null;
                }
            }

            // Call this after login, after adding/deleting a category, or on page load
            document.addEventListener('DOMContentLoaded', function() {
                let currentToken = localStorage.getItem('token');
                if (currentToken) {
                    showFeed();
                    startPeriodicFeedRefresh();
                }
            });
            
            // Digital clock function
            function updateClock() {
                const now = new Date();
                const timeString = now.toLocaleTimeString('en-US', { 
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
                const dateString = now.toLocaleDateString('en-US', {
                    weekday: 'short',
                    month: 'short',
                    day: 'numeric'
                });
                document.getElementById('digital-clock').textContent = `${dateString} ${timeString}`;
            }
            
            // Update clock every second
            setInterval(updateClock, 1000);
            updateClock(); // Initial call
            
            function toggleForm(type) {
                document.getElementById('login-form').classList.remove('active');
                document.getElementById('signup-form').classList.remove('active');
                document.getElementById(type + '-form').classList.add('active');
            }
            
            async function login() {
                const username = document.getElementById('login-username').value;
                const password = document.getElementById('login-password').value;
                
                try {
                    const response = await fetch('/auth/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ username, password })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        localStorage.setItem('token', data.access_token);
                        showFeed();
                        startPeriodicFeedRefresh();
                    } else {
                        showError(data.detail);
                    }
                } catch (error) {
                    showError('Login failed. Please try again.');
                }
            }
            
            async function signup() {
                const username = document.getElementById('signup-username').value;
                const email = document.getElementById('signup-email').value;
                const password = document.getElementById('signup-password').value;
                
                try {
                    const response = await fetch('/auth/signup', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ username, email, password })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        localStorage.setItem('token', data.access_token);
                        showFeed();
                        startPeriodicFeedRefresh();
                    } else {
                        showError(data.detail);
                    }
                } catch (error) {
                    showError('Signup failed. Please try again.');
                }
            }
            
            let currentOffset = 0;
            const FEED_LIMIT = 10;
            let currentCategoryFilter = null;

            async function showFeed(offset = 0, categoryFilter = null) {
                const token = localStorage.getItem('token');
                if (!token) return;
                currentOffset = offset;
                currentCategoryFilter = categoryFilter;
                try {
                    // Fetch user info for header
                    let userResp = await fetch('/auth/me', {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    let username = '';
                    if (userResp.ok) {
                        const userData = await userResp.json();
                        username = userData.username;
                    }
                    // Set header
                    const headerTitle = document.getElementById('feed-header-title');
                    if (headerTitle && username) {
                        headerTitle.textContent = `Feed for ${escapeHtml(username)}`;
                    }
                    let url = `/feed?limit=${FEED_LIMIT}&offset=${offset}`;
                    if (categoryFilter) {
                        url += `&category=${encodeURIComponent(categoryFilter)}`;
                    }
                    const response = await fetch(url, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    if (response.ok) {
                        const feedItems = await response.json();
                        console.log('[DEBUG] Feed API returned:', feedItems.length, 'items');
                        console.log('[DEBUG] Feed items:', feedItems);
                        
                        // Check for Reddit items specifically
                        const redditItems = feedItems.filter(item => item.source && item.source.includes('Reddit'));
                        console.log('[DEBUG] Reddit items found:', redditItems.length);
                        redditItems.forEach(item => {
                            console.log('[DEBUG] Reddit item:', {id: item.id, title: item.title, category: item.category, source: item.source});
                        });
                        
                        displayFeed(feedItems);
                        updatePaginationControls(feedItems.length);
                        loadCategories();
                        document.getElementById('auth-container').style.display = 'none';
                        document.getElementById('feed-container').style.display = 'block';
                    } else {
                        localStorage.removeItem('token');
                        showError('Session expired. Please sign in again.');
                    }
                } catch (error) {
                    showError('Failed to load feed.');
                }
            }

            function updatePaginationControls(feedLength) {
                const controls = document.getElementById('pagination-controls');
                controls.innerHTML = '';
                
                // Calculate current page and total pages
                const currentPage = Math.floor(currentOffset / FEED_LIMIT) + 1;
                const totalPages = Math.ceil(feedLength / FEED_LIMIT) + (feedLength === FEED_LIMIT ? 1 : 0);
                
                // Previous button
                const prevBtn = document.createElement('button');
                prevBtn.textContent = '← Previous';
                prevBtn.disabled = currentOffset === 0;
                prevBtn.onclick = () => showFeed(Math.max(0, currentOffset - FEED_LIMIT), currentCategoryFilter);
                prevBtn.style.cssText = 'background: #a8d5ba; color: #2c3e50; border: none; border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: 500; cursor: pointer; transition: all 0.2s; margin-right: 10px;';
                if (prevBtn.disabled) prevBtn.style.opacity = '0.5';
                controls.appendChild(prevBtn);
                
                // Page numbers
                const pageInfo = document.createElement('span');
                pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
                pageInfo.style.cssText = 'color: #666; font-size: 14px; font-weight: 500; margin: 0 15px;';
                controls.appendChild(pageInfo);
                
                // Next button
                const nextBtn = document.createElement('button');
                nextBtn.textContent = 'Next →';
                nextBtn.disabled = feedLength < FEED_LIMIT;
                nextBtn.onclick = () => showFeed(currentOffset + FEED_LIMIT, currentCategoryFilter);
                nextBtn.style.cssText = 'background: #a8d5ba; color: #2c3e50; border: none; border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: 500; cursor: pointer; transition: all 0.2s; margin-left: 10px;';
                if (nextBtn.disabled) nextBtn.style.opacity = '0.5';
                controls.appendChild(nextBtn);
            }
            
            async function loadCategories() {
                const token = localStorage.getItem('token');
                if (!token) return;
                
                try {
                    const response = await fetch('/user/categories', {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    
                    if (response.ok) {
                        const categories = await response.json();
                        displayCategories(categories);
                    }
                } catch (error) {
                    console.error('Failed to load categories:', error);
                }
            }
            
        

            function displayCategories(categories) {
                const container = document.getElementById('categories-list');
                container.innerHTML = '';
                
                if (categories.length === 0) {
                    container.innerHTML = '<p style="color: #666; font-style: italic;">No categories yet. Add your first category below!</p>';
                    return;
                }
                
                categories.forEach(category => {
                    const categoryDiv = document.createElement('div');
                    categoryDiv.className = 'category-item';
                    // Use short_summary for display if available, else fallback to category_name
                    const displayName = category.short_summary && category.short_summary.trim() ? category.short_summary : category.category_name;
                    const escapedDisplayName = escapeHtml(displayName);
                    categoryDiv.innerHTML = `
                        <span class="category-name" data-category="${escapedDisplayName}" style="cursor: pointer; color: #a8d5ba; text-decoration: underline;">${escapedDisplayName}</span>
                        <button class="delete-category" onclick="deleteCategory(${category.id})">×</button>
                    `;
                    container.appendChild(categoryDiv);
                });
                
                // Add event listeners for category names
                setTimeout(() => {
                    document.querySelectorAll('.category-name').forEach(cat => {
                        cat.addEventListener('click', function() {
                            const category = this.getAttribute('data-category');
                            filterByCategory(category);
                        });
                    });
                }, 50);
            }
            
            async function addCategory() {
                const token = localStorage.getItem('token');
                if (!token) return;
                
                const categoryName = document.getElementById('new-category').value.trim();
                if (!categoryName) {
                    showError('Please enter a category name.');
                    return;
                }
                try {
                    const response = await fetch('/user/categories', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ category_name: categoryName })
                    });
                    const data = await response.json();
                    if (response.ok) {
                        document.getElementById('new-category').value = '';
                        loadCategories();
                        showSuccess('Category added successfully! Generating your feed...');
                        // Trigger feed generation for this user
                        await triggerFeedGeneration();
                        // Refresh the feed after generation
                        await showFeed(0, null);
                    } else {
                        showError(data.detail);
                    }
                } catch (error) {
                    showError('Failed to add category.');
                }
            }

            async function triggerFeedGeneration() {
                const token = localStorage.getItem('token');
                if (!token) return;
                try {
                    // Get current user info to get user_id
                    const userResp = await fetch('/auth/me', {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    if (!userResp.ok) return;
                    const userData = await userResp.json();
                    
                    // Call the ingestion endpoint with correct format
                    const resp = await fetch(`/api/ingestion/ingest/perplexity?user_id=${userData.id}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    if (resp.ok) {
                        const data = await resp.json();
                        // Optionally poll for completion if needed
                        if (data.task_id) {
                            await pollTaskCompletion(data.task_id);
                        }
                    }
                } catch (error) {
                    // Optionally show error
                    console.error('Failed to trigger feed generation:', error);
                }
            }

            async function deleteCategory(categoryId) {
                const token = localStorage.getItem('token');
                if (!token) return;
                if (!confirm('Are you sure you want to delete this category?')) {
                    return;
                }
                try {
                    const response = await fetch(`/user/categories/${categoryId}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    const data = await response.json();
                    if (response.ok) {
                        loadCategories();
                        showSuccess('Category deleted successfully!');
                        // Refresh the feed to remove items from this category
                        await showFeed(0, null);
                    } else {
                        showError(data.detail);
                    }
                } catch (error) {
                    showError('Failed to delete category.');
                }
            }
            


            function updateAllFeedAges() {
                // For each feed-item, update the age label
                const feedItems = document.querySelectorAll('.feed-item');
                console.log(`Updating ages for ${feedItems.length} feed items`);
                
                feedItems.forEach((itemDiv, index) => {
                    const publishedAt = itemDiv.getAttribute('data-published-at');
                    const ageId = itemDiv.getAttribute('data-age-id');
                    
                    if (publishedAt && ageId) {
                        const ageDiv = document.getElementById(ageId);
                        if (ageDiv) {
                            const publishedDate = new Date(publishedAt);
                            const newAge = timeAgo(publishedDate);
                            ageDiv.textContent = newAge;
                            console.log(`Updated age for item ${index}: ${newAge}`);
                        } else {
                            console.log(`Age div not found for item ${index}, ageId: ${ageId}`);
                        }
                    } else {
                        console.log(`Missing data for item ${index}: publishedAt=${publishedAt}, ageId=${ageId}`);
                    }
                });
            }
            
            // Update feed ages every minute and also immediately when feed loads
            setInterval(updateAllFeedAges, 60000);
            
            // Also update ages immediately when feed is displayed
            function displayFeed(items) {
                const container = document.getElementById('feed-items');
                container.innerHTML = '';
                
                // Add category filter header if filtering
                if (currentCategoryFilter) {
                    const filterHeader = document.createElement('div');
                    filterHeader.style.cssText = 'background:#f8f9fa;padding:15px;border-radius:10px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;';
                    const escapedCategoryFilter = escapeHtml(currentCategoryFilter);
                    filterHeader.innerHTML = `
                        <span style="font-weight:600;color:#333;">Showing feeds from: <span style="color:#a8d5ba;">${escapedCategoryFilter}</span></span>
                        <button id="clear-filter-btn" style="background:#f8d7da;color:#721c24;border:none;border-radius:6px;padding:4px 8px;font-size:12px;font-weight:500;cursor:pointer;transition:all 0.2s;">Clear Filter</button>
                    `;
                    container.appendChild(filterHeader);
                }
                
                if (items.length === 0) {
                    const emptyDiv = document.createElement('div');
                    emptyDiv.style.cssText = 'text-align:center;padding:40px;color:#666;font-style:italic;background:white;border-radius:15px;box-shadow:0 2px 8px rgba(0,0,0,0.05);';
                    emptyDiv.innerHTML = 'No feed items found. Try refreshing your briefings!';
                    container.appendChild(emptyDiv);
                    return;
                }
                
                items.forEach((item, idx) => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'feed-item';
                    let published = '';
                    let age = '';
                    let publishedDate = null;
                    if (item.published_at) {
                        publishedDate = new Date(item.published_at);
                        published = formatFullDate(publishedDate);
                        age = timeAgo(publishedDate);
                    }
                    // Combine summary and content for display
                    let feedText = '';
                    if (item.summary) {
                        feedText += item.summary || '';
                    }
                    if (item.content) {
                        if (feedText) {
                            feedText += ' ' + (item.content || '');
                        } else {
                            feedText += item.content || '';
                        }
                    }
                    // Card layout with expandable text
                    const textId = `feed-card-text-${idx}`;
                    const moreId = `feed-card-more-${idx}`;
                    const ageId = `feed-card-age-${idx}`;
                    let needsMore = false;
                    if (feedText.length > 500) needsMore = true;
                    // Use short_summary for display if available, else fallback to category
                    let tagName = item.short_summary && item.short_summary.trim() ? item.short_summary : (item.category || 'Uncategorized');
                    console.log(`[DEBUG] Feed item ${item.id}: category='${item.category}', short_summary='${item.short_summary}', final tagName='${tagName}'`);
                    // Special Reddit card rendering
                    if (item.source && item.source.startsWith('Reddit r/')) {
                        itemDiv.innerHTML = `
                            <div class="reddit-card">
                                <!-- Reddit Card Header with Category Tag -->
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <span style="background: #ff4500; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; cursor: pointer;" data-category="${escapeHtml(tagName)}" class="category-tag">${escapeHtml(tagName)}</span>
                                        <span style="color: #666; font-size: 0.85em;">•</span>
                                        <span style="color: #666; font-size: 0.85em;">${escapeHtml(item.source || 'Unknown')}</span>
                                    </div>
                                    <div style="text-align: right; font-size: 0.8em; color: #999;">
                                        <div id="${ageId}">${age || 'Unknown time'}</div>
                                        <div style="font-size: 0.95em; margin-top: 2px;">${published}</div>
                                    </div>
                                </div>
                                <!-- Reddit Card Content -->
                                <div class="reddit-title">${escapeHtml(item.title)}</div>
                                <div class="reddit-top-comment">${item.content ? `<span style='color:#888;font-size:0.95em;'>Top comment:</span> ${escapeHtml(item.content)}` : ''}</div>
                                <div class="reddit-meta">
                                    <a href="${escapeHtml(item.url)}" target="_blank">View on Reddit →</a>
                                </div>
                            </div>
                        `;
                    } else {
                        // Default card rendering
                        itemDiv.innerHTML = `
                            <div style="display: flex; flex-direction: column;">
                                <!-- Card Header -->
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <span style="background: #a8d5ba; color: #2c3e50; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; cursor: pointer;" data-category="${escapeHtml(tagName)}" class="category-tag">${escapeHtml(tagName)}</span>
                                        <span style="color: #666; font-size: 0.85em;">•</span>
                                        <span style="color: #666; font-size: 0.85em;">${escapeHtml(item.source || 'Unknown')}</span>
                                    </div>
                                    <div style="text-align: right; font-size: 0.8em; color: #999;">
                                        <div id="${ageId}">${age || 'Unknown time'}</div>
                                        <div style="font-size: 0.95em; margin-top: 2px;">${published}</div>
                                    </div>
                                </div>
                                <!-- Card Content -->
                                <div style="display: flex; flex-direction: column;">
                                    <div id="${textId}" class="feed-card-text">${escapeHtml(feedText)}</div>
                                    ${needsMore ? `<span id="${moreId}" class="feed-card-more" data-text-id="${textId}" data-more-id="${moreId}">More</span>` : ''}
                                </div>
                                <!-- Card Footer -->
                                ${item.url ? `<div style="display: flex; justify-content: flex-end; align-items: center; margin-top: 18px;">
                                    <a href="${escapeHtml(item.url)}" target="_blank" style="color: #a8d5ba; text-decoration: none; font-size: 0.85em; font-weight: 500;">Read More →</a>
                                </div>` : ''}
                            </div>
                        `;
                    }
                    // Store published date as data attribute for updating age
                    if (publishedDate) {
                        itemDiv.setAttribute('data-published-at', publishedDate.toISOString());
                        itemDiv.setAttribute('data-age-id', ageId);
                    }
                    container.appendChild(itemDiv);
                });
                
                // Update ages immediately after displaying feed
                setTimeout(updateAllFeedAges, 100);
                
                // Add event listeners for category tags and more buttons
                setTimeout(() => {
                    // Add event listeners for category tags
                    document.querySelectorAll('.category-tag').forEach(tag => {
                        tag.addEventListener('click', function() {
                            const category = this.getAttribute('data-category');
                            filterByCategory(category);
                        });
                    });
                    
                    // Add event listeners for more buttons
                    document.querySelectorAll('.feed-card-more').forEach(btn => {
                        btn.addEventListener('click', function() {
                            const textId = this.getAttribute('data-text-id');
                            const moreId = this.getAttribute('data-more-id');
                            toggleFeedCardText(textId, moreId);
                        });
                    });
                    
                    // Add event listener for clear filter button
                    const clearFilterBtn = document.getElementById('clear-filter-btn');
                    if (clearFilterBtn) {
                        clearFilterBtn.addEventListener('click', clearCategoryFilter);
                    }
                }, 50);
            }

            function filterByCategory(category) {
                showFeed(0, category);
            }

            function clearCategoryFilter() {
                showFeed(0, null);
            }
            
            function timeAgo(date) {
                const now = new Date();
                const seconds = Math.floor((now - date) / 1000);
                const minutes = Math.floor(seconds / 60);
                if (minutes < 1) return `1 minute ago`; // Minimum resolution is 1 minute
                if (minutes < 120) return `${minutes} minutes ago`; // Show minutes for anything less than 2 hours
                const hours = Math.floor(minutes / 60);
                if (hours < 24) return `${hours} hours ago`;
                const days = Math.floor(hours / 24);
                return `${days} days ago`;
            }
            
            function logout() {
                localStorage.removeItem('token');
                document.getElementById('auth-container').style.display = 'block';
                document.getElementById('feed-container').style.display = 'none';
                document.getElementById('login-form').classList.add('active');
                document.getElementById('signup-form').classList.remove('active');
                stopPeriodicFeedRefresh();
            }
            
            function showError(message) {
                // Check if we're in the feed container
                const feedContainer = document.getElementById('feed-container');
                if (feedContainer.style.display !== 'none') {
                    // Show error in feed container
                    let errorDiv = feedContainer.querySelector('.error');
                    if (!errorDiv) {
                        errorDiv = document.createElement('div');
                        errorDiv.className = 'error';
                        errorDiv.style.cssText = 'color: #ff4757; margin: 10px 0; padding: 10px; background: #ffe6e6; border-radius: 5px;';
                        feedContainer.insertBefore(errorDiv, feedContainer.firstChild);
                    }
                    errorDiv.textContent = message;
                    setTimeout(() => {
                        errorDiv.remove();
                    }, 5000);
                    return;
                }
                
                // Show error in login/signup form
                const activeForm = document.querySelector('.form-container.active');
                let errorDiv = activeForm.querySelector('.error');
                if (!errorDiv) {
                    errorDiv = document.createElement('div');
                    errorDiv.className = 'error';
                    activeForm.appendChild(errorDiv);
                }
                errorDiv.textContent = message;
            }
            
            function showSuccess(message) {
                // Check if we're in the feed container
                const feedContainer = document.getElementById('feed-container');
                if (feedContainer.style.display !== 'none') {
                    // Show success in feed container
                    let successDiv = feedContainer.querySelector('.success');
                    if (!successDiv) {
                        successDiv = document.createElement('div');
                        successDiv.className = 'success';
                        successDiv.style.cssText = 'color: #2ed573; margin: 10px 0; padding: 10px; background: #e6ffe6; border-radius: 5px;';
                        feedContainer.insertBefore(successDiv, feedContainer.firstChild);
                    }
                    successDiv.textContent = message;
                    setTimeout(() => {
                        successDiv.remove();
                    }, 5000);
                    return;
                }
                
                // Show success in login/signup form
                const activeForm = document.querySelector('.form-container.active');
                let successDiv = activeForm.querySelector('.success');
                if (!successDiv) {
                    successDiv = document.createElement('div');
                    successDiv.className = 'success';
                    activeForm.appendChild(successDiv);
                }
                successDiv.textContent = message;
            }

            async function refreshBriefings() {
                const token = localStorage.getItem('token');
                if (!token) return;
                
                // Show loading state
                const refreshBtn = document.getElementById('refresh-briefings-btn');
                const originalText = refreshBtn.textContent;
                refreshBtn.textContent = '🔄 Refreshing...';
                refreshBtn.disabled = true;
                
                try {
                    // Trigger the ingestion
                    const response = await fetch('/api/ingestion/ingest/perplexity', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        showSuccess('Briefings refresh started! Waiting for completion...');
                        
                        // Poll for task completion
                        await pollTaskCompletion(data.task_id);
                        
                        // Reload the feed with current filter state
                        await showFeed(currentOffset, currentCategoryFilter);
                        showSuccess('Briefings refreshed successfully!');
                    } else {
                        const data = await response.json();
                        showError(data.detail || 'Failed to trigger refresh.');
                    }
                } catch (error) {
                    showError('Failed to trigger refresh.');
                } finally {
                    // Restore button state
                    refreshBtn.textContent = originalText;
                    refreshBtn.disabled = false;
                }
            }
            
            async function pollTaskCompletion(taskId) {
                const maxAttempts = 60; // 5 minutes (60 * 5 seconds)
                let attempts = 0;
                
                while (attempts < maxAttempts) {
                    try {
                        const response = await fetch(`/api/ingestion/task/${taskId}`, {
                            headers: {
                                'Authorization': `Bearer ${localStorage.getItem('token')}`
                            }
                        });
                        
                        if (response.ok) {
                            const taskData = await response.json();
                            
                            if (taskData.status === 'SUCCESS') {
                                console.log('Task completed successfully');
                                return;
                            } else if (taskData.status === 'FAILURE') {
                                throw new Error('Task failed: ' + (taskData.result || 'Unknown error'));
                            }
                            // If still running, continue polling
                        }
                    } catch (error) {
                        console.error('Error polling task status:', error);
                    }
                    
                    // Wait 5 seconds before next poll
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    attempts++;
                }
                
                throw new Error('Task timed out after 5 minutes');
            }

            function formatFullDate(date) {
                // Format: Mon, Dec 25, 2023 14:30:45 (24-hour)
                return date.toLocaleString('en-US', {
                    weekday: 'short',
                    year: 'numeric',
                    month: 'short',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false
                });
            }

            function toggleFeedCardText(textId, moreId) {
                const textDiv = document.getElementById(textId);
                const moreSpan = document.getElementById(moreId);
                if (textDiv.classList.contains('expanded')) {
                    textDiv.classList.remove('expanded');
                    moreSpan.textContent = 'More';
                } else {
                    textDiv.classList.add('expanded');
                    moreSpan.textContent = 'Less';
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "My Briefings Feed Service"}

# Authentication endpoints
@app.post("/auth/signup", response_model=User)
async def signup(user: UserCreate):
    """Create a new user account"""
    db = SessionLocal()
    
    # Check if username already exists
    existing_user = db.query(UserDB).filter(UserDB.username == user.username).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists
    existing_email = db.query(UserDB).filter(UserDB.email == user.email).first()
    if existing_email:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = UserDB(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create default category for new user
    default_category = UserCategoryDB(
        user_id=db_user.id,
        category_name="What's the biggest headlines from around the world?"
    )
    
    db.add(default_category)
    db.commit()
    
    # Trigger ingestion for the new user with default category
    try:
        import requests
        # Call ingestion service directly since this is server-side code
        ingestion_response = requests.post(
            f"{INGESTION_SERVICE_URL}/ingest/perplexity",
            params={"user_id": db_user.id},
            timeout=5
        )
        if ingestion_response.status_code == 200:
            print(f"Triggered ingestion for new user {db_user.id} with default category")
        else:
            print(f"Failed to trigger ingestion for new user {db_user.id}: {ingestion_response.status_code}")
    except Exception as e:
        print(f"Error triggering ingestion for new user {db_user.id}: {e}")
    
    db.close()
    
    return User(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        created_at=to_utc_z(db_user.created_at)
    )

@app.post("/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Authenticate user and return JWT token"""
    user = authenticate_user(user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return User(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        created_at=to_utc_z(datetime.fromisoformat(current_user["created_at"])) if current_user["created_at"] else None
    )

@app.get("/auth/users", response_model=List[User])
async def get_all_users(current_user: dict = Depends(get_current_user)):
    """Get all users in the system (admin function)"""
    db = SessionLocal()
    try:
        users = db.query(UserDB).order_by(UserDB.created_at.desc()).all()
        result = []
        for user in users:
            result.append(User(
                id=user.id,
                username=user.username,
                email=user.email,
                created_at=to_utc_z(user.created_at)
            ))
        return result
    finally:
        db.close()

@app.delete("/auth/user")
async def delete_user_account(current_user: dict = Depends(get_current_user)):
    """Delete the current user's account and all associated data"""
    db = SessionLocal()
    try:
        user_id = current_user["id"]
        
        # Get user's categories
        user_categories = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id
        ).all()
        
        category_names = [cat.category_name for cat in user_categories]
        
        # Delete feed items for user's categories
        deleted_feed_count = 0
        if category_names:
            deleted_feed_count = db.query(FeedItemDB).filter(
                FeedItemDB.category.in_(category_names)
            ).delete()
        
        # Delete user's categories
        deleted_categories_count = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id
        ).delete()
        
        # Delete the user account
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if user:
            db.delete(user)
        
        db.commit()
        
        return {
            "message": "User account and all associated data deleted successfully",
            "feed_items_deleted": deleted_feed_count,
            "categories_deleted": deleted_categories_count,
            "user_deleted": True
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user account: {str(e)}")
    finally:
        db.close()

@app.get("/feed", response_model=List[FeedItem])
async def get_feed(limit: int = 10, offset: int = 0, category: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get feed items with pagination (protected route)"""
    db = SessionLocal()
    try:
        # If a category is specified, filter by it (existing behavior)
        if category:
            # Get user categories to understand the mapping
            user_categories = db.query(UserCategoryDB).filter(UserCategoryDB.user_id == current_user["id"]).all()
            
            # Create mappings for both directions
            short_summary_to_category = {cat.short_summary: cat.category_name for cat in user_categories if cat.short_summary}
            category_to_short_summary = {cat.category_name: cat.short_summary for cat in user_categories if cat.short_summary}
            
            # Determine what we're filtering by
            # If the category parameter matches a short_summary, we need to find items with that short_summary
            # If the category parameter matches a category_name, we need to find items with that category_name
            # We need to check both possibilities
            
            category_filters = []
            
            # Check if the category parameter is a short_summary
            if category in short_summary_to_category.values():
                category_filters.append(category)  # This will match Reddit items saved with short_summary
            
            # Check if the category parameter is a category_name
            if category in category_to_short_summary.keys():
                category_filters.append(category)  # This will match Perplexity items saved with category_name
            
            # Also check the reverse mapping
            if category in short_summary_to_category:
                category_filters.append(short_summary_to_category[category])  # Map short_summary to category_name
            
            # Remove duplicates
            category_filters = list(set(category_filters))
            
            print(f"[DEBUG] Filtering: received '{category}', using filters: {category_filters}")
            
            if category_filters:
                query = db.query(FeedItemDB).filter(FeedItemDB.category.in_(category_filters))
            else:
                # Fallback: try exact match
                query = db.query(FeedItemDB).filter(FeedItemDB.category == category)
        else:
            # Check if user has any categories
            user_categories = db.query(UserCategoryDB).filter(UserCategoryDB.user_id == current_user["id"]).all()
            if user_categories:
                # Create a list of all possible category values to filter by
                # This includes both short_summary and category_name to handle both Reddit and Perplexity items
                category_filters = []
                for cat in user_categories:
                    # Add short_summary if available (for Reddit items)
                    if cat.short_summary:
                        category_filters.append(cat.short_summary)
                    # Add category_name (for Perplexity items)
                    category_filters.append(cat.category_name)
                # Remove duplicates while preserving order
                category_filters = list(dict.fromkeys(category_filters))
                query = db.query(FeedItemDB).filter(FeedItemDB.category.in_(category_filters))
            else:
                # No user categories, show only the global feed for the single common category
                query = db.query(FeedItemDB).filter(FeedItemDB.category == "What is the happening in the world right now?")
        query = query.order_by(FeedItemDB.published_at.desc(), FeedItemDB.created_at.desc())
        items = query.offset(offset).limit(limit).all()
        # Build a mapping from category_name to short_summary for this user
        user_category_map = {cat.category_name: cat.short_summary for cat in db.query(UserCategoryDB).filter(UserCategoryDB.user_id == current_user["id"]).all()}
        print(f"[DEBUG] User category map: {user_category_map}")
        result = []
        for item in items:
            # Ensure published_at and created_at are always UTC ISO strings with 'Z'
            published_at_str = to_utc_z(item.published_at)
            created_at_str = to_utc_z(item.created_at)
            # Attach short_summary if available for this category
            short_summary = user_category_map.get(item.category)
            print(f"[DEBUG] Feed item category: '{item.category}' -> short_summary: '{short_summary}'")
            result.append(FeedItem(
                id=item.id,
                summary=item.summary,
                content=item.content,
                url=item.url,
                source=item.source,
                published_at=published_at_str,
                created_at=created_at_str,
                category=item.category,
                short_summary=short_summary
            ))
        return result
    finally:
        db.close()

@app.get("/feed/{item_id}", response_model=FeedItem)
async def get_feed_item(item_id: int, current_user: dict = Depends(get_current_user)):
    """Get a specific feed item by ID (protected route)"""
    db = SessionLocal()
    try:
        item = db.query(FeedItemDB).filter(FeedItemDB.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Feed item not found")
        
        # Build a mapping from category_name to short_summary for this user
        user_category_map = {cat.category_name: cat.short_summary for cat in db.query(UserCategoryDB).filter(UserCategoryDB.user_id == current_user["id"]).all()}
        
        # Ensure published_at and created_at are always UTC ISO strings with 'Z'
        published_at_str = to_utc_z(item.published_at)
        created_at_str = to_utc_z(item.created_at)
        
        # Attach short_summary if available for this category
        short_summary = user_category_map.get(item.category)
        
        return FeedItem(
            id=item.id,
            summary=item.summary,
            content=item.content,
            url=item.url,
            source=item.source,
            published_at=published_at_str,
            created_at=created_at_str,
            category=item.category,
            short_summary=short_summary
        )
    finally:
        db.close()

# User Categories endpoints
@app.get("/user/categories", response_model=List[UserCategory])
async def get_user_categories(current_user: dict = Depends(get_current_user)):
    """Get all categories for the current user"""
    db = SessionLocal()
    
    categories = db.query(UserCategoryDB).filter(
        UserCategoryDB.user_id == current_user["id"]
    ).order_by(UserCategoryDB.created_at.desc()).all()
    
    result = []
    for category in categories:
        result.append(UserCategory(
            id=category.id,
            user_id=category.user_id,
            category_name=category.category_name,
            short_summary=category.short_summary,
            subreddits=category.subreddits,
            twitter=category.twitter,
            created_at=to_utc_z(category.created_at)
        ))
    
    db.close()
    return result

@app.post("/user/categories", response_model=UserCategory)
async def create_user_category(
    category: UserCategoryCreate, 
    current_user: dict = Depends(get_current_user)
):
    """Create a new category for the current user (max 5 categories)"""
    db = SessionLocal()
    
    # Check if user already has 5 categories
    existing_count = db.query(UserCategoryDB).filter(
        UserCategoryDB.user_id == current_user["id"]
    ).count()
    
    if existing_count >= 5:
        db.close()
        raise HTTPException(status_code=400, detail="Maximum of 5 categories allowed per user")
    
    # Check if category name already exists for this user
    existing_category = db.query(UserCategoryDB).filter(
        UserCategoryDB.user_id == current_user["id"],
        UserCategoryDB.category_name == category.category_name
    ).first()
    
    if existing_category:
        db.close()
        raise HTTPException(status_code=400, detail="Category already exists")
    
    # Validate category name length
    if len(category.category_name) > 140:
        db.close()
        raise HTTPException(status_code=400, detail="Category name must be 140 characters or less")
    
    # Call Perplexity API to get derivatives (includes summary + additional metadata)
    import requests
    import json
    short_summary = None
    subreddits = None
    twitter = None
    try:
        perplexity_api_url = f"{INGESTION_SERVICE_URL}/perplexity/derivatives"
        prompt = (
            f'Consider the phrase "{category.category_name}". For this phrase, please respond ONLY in JSON to the following questions: '
            '1. What is an up to 4 word summary of this phrase? The JSON key for this should be "summary" and the value should be a string. '
            '2. What are the most popular subreddits that discuss the topic in this phrase? The JSON key for this should be "reddit" and the value should be a list of subreddit names as strings. '
            '3. What are the most popular twitter handles and hashtags to learn about the topic in the phrase on twitter? The JSON key for this should be "twitter" and the value should be a list of strings, each string being either a handle (starting with @) or a hashtag (starting with #).'
            ' Respond ONLY with a single JSON object with these three keys: "summary", "reddit", and "twitter".'
        )
        print(f"[DEBUG] Calling derivatives API with category: {category.category_name}")
        resp = requests.post(perplexity_api_url, json={"text": category.category_name}, timeout=15)
        print(f"[DEBUG] Derivatives API response status: {resp.status_code}")
        print(f"[DEBUG] Derivatives API response text: {resp.text[:500]}")
        if resp.ok:
            data = resp.json()
            print(f"[DEBUG] Derivatives API parsed data: {data}")
            short_summary = data.get("summary")
            if short_summary:
                short_summary = " ".join(short_summary.split()[:4])
            subreddits = json.dumps(data.get("reddit", []))
            twitter = json.dumps(data.get("twitter", []))
            print(f"[DEBUG] Extracted derivatives - summary: {short_summary}, subreddits: {subreddits}, twitter: {twitter}")
        else:
            print(f"[ERROR] Derivatives API failed with status {resp.status_code}: {resp.text}")
            short_summary = None
            subreddits = None
            twitter = None
    except Exception as e:
        print(f"[ERROR] Exception in derivatives API call: {e}")
        short_summary = None
        subreddits = None
        twitter = None
    db_category = UserCategoryDB(
        user_id=current_user["id"],
        category_name=category.category_name,
        short_summary=short_summary,
        subreddits=subreddits,
        twitter=twitter
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    # Trigger Reddit ingestion for this specific user
    try:
        print(f"[DEBUG] Triggering Reddit ingestion for user {current_user['id']} after category creation")
        reddit_response = requests.post(
            f"{INGESTION_SERVICE_URL}/ingest/reddit/user/{current_user['id']}",
            timeout=5
        )
        if reddit_response.status_code == 200:
            print(f"[DEBUG] Reddit ingestion for user {current_user['id']} triggered successfully")
        else:
            print(f"[ERROR] Failed to trigger Reddit ingestion for user {current_user['id']}: {reddit_response.status_code}")
    except Exception as e:
        print(f"[ERROR] Exception triggering Reddit ingestion for user {current_user['id']}: {e}")
    
    db.close()
    return UserCategory(
        id=db_category.id,
        user_id=db_category.user_id,
        category_name=db_category.category_name,
        short_summary=db_category.short_summary,
        subreddits=db_category.subreddits,
        twitter=db_category.twitter,
        created_at=to_utc_z(db_category.created_at)
    )

@app.delete("/user/categories/{category_id}")
async def delete_user_category(category_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a category for the current user and all associated feed items"""
    db = SessionLocal()
    try:
        category = db.query(UserCategoryDB).filter(
            UserCategoryDB.id == category_id,
            UserCategoryDB.user_id == current_user["id"]
        ).first()
        if not category:
            db.close()
            raise HTTPException(status_code=404, detail="Category not found")
        # Delete all feed items for this user and category
        deleted_count = db.query(FeedItemDB).filter(
            FeedItemDB.category == category.category_name
        ).delete()
        db.delete(category)
        db.commit()
        return {"message": "Category and associated feed items deleted successfully", "feed_items_deleted": deleted_count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting category and feed items: {str(e)}")
    finally:
        db.close()

# Legacy endpoints (keeping for backward compatibility)
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

# Feed data deletion APIs
@app.delete("/feed/delete/user/{user_id}")
async def delete_feed_data_for_user(
    user_id: int, 
    current_user: dict = Depends(get_current_user),
    confirm: bool = Query(..., description="Must be true to confirm deletion")
):
    """Delete all feed data for a specific user (admin only)"""
    # Check if current user is admin (you can modify this logic based on your admin criteria)
    if current_user["id"] != 1:  # Assuming user ID 1 is admin
        raise HTTPException(status_code=403, detail="Only admin users can delete feed data")
    
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    db = SessionLocal()
    try:
        # Get user's categories
        user_categories = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id
        ).all()
        
        category_names = [cat.category_name for cat in user_categories]
        
        # Delete feed items for user's categories
        deleted_count = 0
        if category_names:
            deleted_count = db.query(FeedItemDB).filter(
                FeedItemDB.category.in_(category_names)
            ).delete()
        
        # Delete user's categories
        categories_deleted = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Successfully deleted feed data for user {user_id}",
            "feed_items_deleted": deleted_count,
            "categories_deleted": categories_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting feed data: {str(e)}")
    finally:
        db.close()

@app.delete("/feed/delete/all")
async def delete_all_feed_data(
    current_user: dict = Depends(get_current_user),
    confirm: bool = Query(..., description="Must be true to confirm deletion")
):
    """Delete all feed data for all users (admin only)"""
    # Check if current user is admin
    if current_user["id"] != 1:  # Assuming user ID 1 is admin
        raise HTTPException(status_code=403, detail="Only admin users can delete all feed data")
    
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    db = SessionLocal()
    try:
        # Delete all feed items
        feed_items_deleted = db.query(FeedItemDB).delete()
        
        # Delete all user categories
        categories_deleted = db.query(UserCategoryDB).delete()
        
        db.commit()
        
        return {
            "message": "Successfully deleted all feed data",
            "feed_items_deleted": feed_items_deleted,
            "categories_deleted": categories_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting all feed data: {str(e)}")
    finally:
        db.close()

@app.delete("/feed/delete/category/{category_name}")
async def delete_feed_data_by_category(
    category_name: str,
    current_user: dict = Depends(get_current_user),
    confirm: bool = Query(..., description="Must be true to confirm deletion")
):
    """Delete all feed data for a specific category (admin only)"""
    # Check if current user is admin
    if current_user["id"] != 1:  # Assuming user ID 1 is admin
        raise HTTPException(status_code=403, detail="Only admin users can delete feed data by category")
    
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    db = SessionLocal()
    try:
        # Delete feed items for the category
        feed_items_deleted = db.query(FeedItemDB).filter(
            FeedItemDB.category == category_name
        ).delete()
        
        # Delete user categories with this name
        categories_deleted = db.query(UserCategoryDB).filter(
            UserCategoryDB.category_name == category_name
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Successfully deleted feed data for category '{category_name}'",
            "feed_items_deleted": feed_items_deleted,
            "categories_deleted": categories_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting feed data: {str(e)}")
    finally:
        db.close()



# Proxy endpoints to ingestion service
@app.post("/api/ingestion/perplexity/derivatives")
async def proxy_perplexity_derivatives(request: Request):
    """Proxy endpoint to forward derivatives requests to ingestion service"""
    try:
        # Get the request body
        body = await request.json()
        print(f"[DEBUG] Proxy derivatives called with body: {body}")
        
        # Forward to ingestion service
        import requests
        ingestion_url = f"{INGESTION_SERVICE_URL}/perplexity/derivatives"
        print(f"[DEBUG] Forwarding to: {ingestion_url}")
        response = requests.post(ingestion_url, json=body, timeout=15)
        print(f"[DEBUG] Proxy derivatives response status: {response.status_code}")
        
        return response.json()
    except Exception as e:
        print(f"[ERROR] Proxy derivatives error: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@app.post("/api/ingestion/ingest/perplexity")
async def proxy_ingest_perplexity(request: Request):
    """Proxy endpoint to forward ingestion requests to ingestion service"""
    try:
        # Get query parameters
        user_id = request.query_params.get("user_id")
        print(f"[DEBUG] Proxy ingestion called with user_id: {user_id}")
        
        # Forward to ingestion service
        import requests
        ingestion_url = f"{INGESTION_SERVICE_URL}/ingest/perplexity"
        if user_id:
            ingestion_url += f"?user_id={user_id}"
        print(f"[DEBUG] Forwarding to: {ingestion_url}")
        
        response = requests.post(ingestion_url, timeout=15)
        print(f"[DEBUG] Proxy ingestion response status: {response.status_code}")
        
        return response.json()
    except Exception as e:
        print(f"[ERROR] Proxy ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@app.get("/api/ingestion/task/{task_id}")
async def proxy_task_status(task_id: str):
    """Proxy endpoint to forward task status requests to ingestion service"""
    try:
        print(f"[DEBUG] Proxy task status called with task_id: {task_id}")
        
        # Forward to ingestion service
        import requests
        ingestion_url = f"{INGESTION_SERVICE_URL}/task/{task_id}"
        print(f"[DEBUG] Forwarding to: {ingestion_url}")
        response = requests.get(ingestion_url, timeout=15)
        print(f"[DEBUG] Proxy task status response status: {response.status_code}")
        
        return response.json()
    except Exception as e:
        print(f"[ERROR] Proxy task status error: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@app.get("/api/ingestion/debug/user-feed/{user_id}")
async def proxy_debug_user_feed(user_id: int):
    """Proxy endpoint to forward debug user feed requests to ingestion service"""
    try:
        print(f"[DEBUG] Proxy debug user feed called with user_id: {user_id}")
        
        # Forward to ingestion service
        import requests
        ingestion_url = f"{INGESTION_SERVICE_URL}/debug/user-feed/{user_id}"
        print(f"[DEBUG] Forwarding to: {ingestion_url}")
        response = requests.get(ingestion_url, timeout=15)
        print(f"[DEBUG] Proxy debug user feed response status: {response.status_code}")
        
        return response.json()
    except Exception as e:
        print(f"[ERROR] Proxy debug user feed error: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 