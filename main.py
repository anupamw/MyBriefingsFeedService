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
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, UniqueConstraint, Float, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import time
import json
import requests

# Load environment variables from .env file
load_dotenv()

# Configuration
INGESTION_SERVICE_URL = os.getenv("INGESTION_SERVICE_URL", "http://my-briefings-ingestion-service:8001")

app = FastAPI(
    title="My Briefings Feed Service",
    description="A FastAPI service for serving personalized news feeds",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="templates/static"), name="static")
templates = Jinja2Templates(directory="templates")

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
    """User model (moved from main.py for shared access)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AISummaryDB(Base):
    """AI-generated summaries for users"""
    __tablename__ = "ai_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    summary_content = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False)
    max_words_requested = Column(Integer, nullable=False)
    categories_covered = Column(JSON)  # Array of category names
    total_feed_items_analyzed = Column(Integer, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(100), default="Perplexity AI")
    is_active = Column(Boolean, default=True)  # For soft deletion
    
    # Index for quick user lookups
    __table_args__ = (
        Index('idx_ai_summaries_user_id', 'user_id'),
        Index('idx_ai_summaries_generated_at', 'generated_at'),
    )

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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    category = Column(String(100))  # Add category field
    
    # AI filtering results
    is_relevant = Column(Boolean, default=True)  # AI-determined relevance (True=relevant, False=irrelevant)
    relevance_reason = Column(Text)  # AI explanation for relevance decision

class UserCategoryDB(Base):
    __tablename__ = "user_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    category_name = Column(String(140), nullable=False)  # Limited to 140 characters
    short_summary = Column(String(50), nullable=True)  # Up to 4-word summary for display
    subreddits = Column(Text, nullable=True)  # JSON string
    twitter = Column(Text, nullable=True)     # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Category preferences
    keywords = Column(JSON)  # Array of keywords for this category
    sources = Column(JSON)  # Preferred sources for this category
    is_active = Column(Boolean, default=True)
    
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
    title: Optional[str] = None
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
async def root(request: Request):
    """Serve the main application page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "My Briefings Feed Service"}

# Authentication endpoints
@app.post("/auth/signup", response_model=Token)
async def signup(user: UserCreate):
    """Create a new user account and return JWT token for automatic login"""
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
    
    # Create JWT token for automatic login after signup
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

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
async def get_feed(limit: int = 30, offset: int = 0, category: Optional[str] = None, randomize: bool = True, current_user: dict = Depends(get_current_user)):
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
        # Get items with standard ordering first
        query = query.order_by(FeedItemDB.published_at.desc(), FeedItemDB.created_at.desc())
        
        # Filter by relevance - only show relevant items in UI
        query = query.filter(FeedItemDB.is_relevant == True)
        
        if randomize:
            # Get more items for better randomization
            items = query.offset(offset).limit(limit * 2).all()
            # Randomize the items to mix up sources and categories
            import random
            random.shuffle(items)
            items = items[:limit]  # Take only the requested limit
        else:
            # Standard ordering without randomization
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
                title=item.title,
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
    """Get a specific feed item by ID (protected route) - only returns relevant items"""
    db = SessionLocal()
    try:
        # Only return relevant items
        item = db.query(FeedItemDB).filter(FeedItemDB.id == item_id, FeedItemDB.is_relevant == True).first()
        if not item:
            raise HTTPException(status_code=404, detail="Feed item not found or not relevant")
        
        # Build a mapping from category_name to short_summary for this user
        user_category_map = {cat.category_name: cat.short_summary for cat in db.query(UserCategoryDB).filter(UserCategoryDB.user_id == current_user["id"]).all()}
        
        # Ensure published_at and created_at are always UTC ISO strings with 'Z'
        published_at_str = to_utc_z(item.published_at)
        created_at_str = to_utc_z(item.created_at)
        
        # Attach short_summary if available for this category
        short_summary = user_category_map.get(item.category)
        
        return FeedItem(
            id=item.id,
            title=item.title,
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
    
    # Trigger Reddit and NewsAPI ingestion for this specific user
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
    
    try:
        print(f"[DEBUG] Triggering NewsAPI ingestion for user {current_user['id']} after category creation")
        newsapi_response = requests.post(
            f"{INGESTION_SERVICE_URL}/ingest/newsapi/user/{current_user['id']}",
            timeout=5
        )
        if newsapi_response.status_code == 200:
            print(f"[DEBUG] NewsAPI ingestion for user {current_user['id']} triggered successfully")
        else:
            print(f"[ERROR] Failed to trigger NewsAPI ingestion for user {current_user['id']}: {newsapi_response.status_code}")
    except Exception as e:
        print(f"[ERROR] Exception triggering NewsAPI ingestion for user {current_user['id']}: {e}")
    
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
        deleted_categories_count = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Successfully deleted feed data for user {user_id}",
            "feed_items_deleted": deleted_count,
            "categories_deleted": deleted_categories_count
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

@app.get("/debug/user-feed-stats/{user_id}")
async def debug_user_feed_stats(user_id: int):
    """Debug endpoint to show feed statistics for a specific user across all ingestion methods"""
    
    db = SessionLocal()
    try:
        # Get user's categories
        user_categories = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id
        ).all()
        
        if not user_categories:
            return {
                "user_id": user_id,
                "message": "No categories found for this user",
                "categories": [],
                "feed_stats": {
                    "perplexity": 0,
                    "reddit": 0,
                    "newsapi": 0,
                    "total": 0
                }
            }
        
        # Get category names for this user
        category_names = [cat.category_name for cat in user_categories]
        
        # Get all feed items for this user's categories using current schema
        feed_items = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names)
        ).all()
        
        # Count items by source field (fallback method for current schema)
        perplexity_count = 0
        reddit_count = 0
        newsapi_count = 0
        other_count = 0
        
        for item in feed_items:
            source = item.source or ""
            if source == "Perplexity AI":
                perplexity_count += 1
            elif source.startswith("Reddit r/"):
                reddit_count += 1
            elif source.startswith("NewsAPI -"):
                newsapi_count += 1
            else:
                other_count += 1
        
        total_count = len(feed_items)
        
        # Get category details
        categories_info = []
        for cat in user_categories:
            # Count items for this specific category
            category_items = db.query(FeedItemDB).filter(
                FeedItemDB.category == cat.category_name
            ).all()
            
            cat_perplexity = sum(1 for item in category_items if item.source == "Perplexity AI")
            cat_reddit = sum(1 for item in category_items if item.source and item.source.startswith("Reddit r/"))
            cat_newsapi = sum(1 for item in category_items if item.source and item.source.startswith("NewsAPI -"))
            cat_other = sum(1 for item in category_items if item.source not in ["Perplexity AI"] and not (item.source and item.source.startswith("Reddit r/")) and not (item.source and item.source.startswith("NewsAPI -")))
            
            categories_info.append({
                "id": cat.id,
                "category_name": cat.category_name,
                "short_summary": cat.short_summary,
                "created_at": to_utc_z(cat.created_at),
                "item_counts": {
                    "perplexity": cat_perplexity,
                    "reddit": cat_reddit,
                    "newsapi": cat_newsapi,
                    "other": cat_other,
                    "total": len(category_items)
                }
            })
        
        # Get recent items (last 10) for each source
        recent_perplexity = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.source == "Perplexity AI"
        ).order_by(FeedItemDB.created_at.desc()).limit(10).all()
        
        recent_reddit = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.source.like('Reddit r/%')
        ).order_by(FeedItemDB.created_at.desc()).limit(10).all()
        
        recent_newsapi = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.source.like('NewsAPI -%')
        ).order_by(FeedItemDB.created_at.desc()).limit(10).all()
        
        def format_recent_items(items):
            return [{
                "id": item.id,
                "title": item.title,
                "source": item.source,
                "category": item.category,
                "created_at": to_utc_z(item.created_at),
                "published_at": to_utc_z(item.published_at)
            } for item in items]
        
        return {
            "user_id": user_id,
            "total_categories": len(user_categories),
            "categories": categories_info,
            "feed_stats": {
                "perplexity": perplexity_count,
                "reddit": reddit_count,
                "newsapi": newsapi_count,
                "other": other_count,
                "total": total_count
            },
            "recent_items": {
                "perplexity": format_recent_items(recent_perplexity),
                "reddit": format_recent_items(recent_reddit),
                "newsapi": format_recent_items(recent_newsapi)
            },
            "generated_at": to_utc_z(datetime.utcnow())
        }
        
    except Exception as e:
        print(f"[ERROR] Debug user feed stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating feed stats: {str(e)}")
    finally:
        db.close()

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

@app.get("/api/ingestion/debug/user-feed-all/{user_id}")
async def proxy_debug_user_feed_all(user_id: int):
    """Proxy endpoint to forward debug user feed ALL requests to ingestion service - NO AUTH REQUIRED"""
    try:
        print(f"[DEBUG] Proxy debug user feed ALL called with user_id: {user_id}")
        
        # Forward to ingestion service
        import requests
        ingestion_url = f"{INGESTION_SERVICE_URL}/debug/user-feed-all/{user_id}"
        print(f"[DEBUG] Forwarding to: {ingestion_url}")
        response = requests.get(ingestion_url, timeout=15)
        print(f"[DEBUG] Proxy debug user feed ALL response status: {response.status_code}")
        
        return response.json()
    except Exception as e:
        print(f"[ERROR] Proxy debug user feed ALL error: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@app.get("/debug/orphaned-feed-items")
async def debug_orphaned_feed_items(limit: int = 50):
    """Debug endpoint to show orphaned feed items (items with categories that don't exist in user_categories)"""
    
    db = SessionLocal()
    try:
        # Get orphaned feed items
        orphaned_items = db.query(FeedItemDB).filter(
            ~FeedItemDB.category.in_(
                db.query(UserCategoryDB.category_name)
            )
        ).order_by(FeedItemDB.created_at.desc()).limit(limit).all()
        
        # Group by category for summary
        category_summary = {}
        for item in orphaned_items:
            if item.category not in category_summary:
                category_summary[item.category] = 0
            category_summary[item.category] += 1
        
        return {
            "total_orphaned_items": len(orphaned_items),
            "category_summary": category_summary,
            "orphaned_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "category": item.category,
                    "source": item.source,
                    "created_at": to_utc_z(item.created_at),
                    "published_at": to_utc_z(item.published_at)
                }
                for item in orphaned_items
            ]
        }
    except Exception as e:
        print(f"[ERROR] Debug orphaned feed items error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting orphaned feed items: {str(e)}")
    finally:
        db.close()

@app.delete("/debug/cleanup-orphaned-feed-items")
async def cleanup_orphaned_feed_items(
    confirm: bool = Query(..., description="Must be true to confirm deletion")
):
    """Clean up orphaned feed items (items with categories that don't exist in user_categories)"""
    
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    db = SessionLocal()
    try:
        # Count orphaned items before deletion
        orphaned_count = db.query(FeedItemDB).filter(
            ~FeedItemDB.category.in_(
                db.query(UserCategoryDB.category_name)
            )
        ).count()
        
        # Delete orphaned feed items
        deleted_count = db.query(FeedItemDB).filter(
            ~FeedItemDB.category.in_(
                db.query(UserCategoryDB.category_name)
            )
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Successfully cleaned up {deleted_count} orphaned feed items",
            "orphaned_items_deleted": deleted_count,
            "total_orphaned_items_found": orphaned_count
        }
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Cleanup orphaned feed items error: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up orphaned feed items: {str(e)}")
    finally:
        db.close()

@app.delete("/debug/cleanup-old-feed-items")
async def cleanup_old_feed_items(
    days_old: int = Query(30, description="Delete items older than this many days"),
    confirm: bool = Query(..., description="Must be true to confirm deletion")
):
    """Clean up old feed items based on age"""
    
    if not confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion with confirm=true")
    
    if days_old < 1:
        raise HTTPException(status_code=400, detail="days_old must be at least 1")
    
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Count old items before deletion
        old_count = db.query(FeedItemDB).filter(
            FeedItemDB.created_at < cutoff_date
        ).count()
        
        # Delete old feed items
        deleted_count = db.query(FeedItemDB).filter(
            FeedItemDB.created_at < cutoff_date
        ).delete()
        
        db.commit()
        
        return {
            "message": f"Successfully cleaned up {deleted_count} feed items older than {days_old} days",
            "old_items_deleted": deleted_count,
            "total_old_items_found": old_count,
            "cutoff_date": to_utc_z(cutoff_date)
        }
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Cleanup old feed items error: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up old feed items: {str(e)}")
    finally:
        db.close()

@app.get("/debug/user-feed-stats/{user_id}")
async def debug_user_feed_stats(user_id: int):
    """Debug endpoint to show feed statistics for a specific user across all ingestion methods"""
    
    db = SessionLocal()
    try:
        # Get user's categories
        user_categories = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id
        ).all()
        
        if not user_categories:
            return {
                "user_id": user_id,
                "message": "No categories found for this user",
                "categories": [],
                "feed_stats": {
                    "perplexity": 0,
                    "reddit": 0,
                    "newsapi": 0,
                    "total": 0
                }
            }
        
        # Get category names for this user
        category_names = [cat.category_name for cat in user_categories]
        
        # Get all feed items for this user's categories using current schema
        feed_items = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names)
        ).all()
        
        # Count items by source field (fallback method for current schema)
        perplexity_count = 0
        reddit_count = 0
        newsapi_count = 0
        other_count = 0
        
        for item in feed_items:
            source = item.source or ""
            if source == "Perplexity AI":
                perplexity_count += 1
            elif source.startswith("Reddit r/"):
                reddit_count += 1
            elif source.startswith("NewsAPI -"):
                newsapi_count += 1
            else:
                other_count += 1
        
        total_count = len(feed_items)
        
        # Get category details
        categories_info = []
        for cat in user_categories:
            # Count items for this specific category
            category_items = db.query(FeedItemDB).filter(
                FeedItemDB.category == cat.category_name
            ).all()
            
            cat_perplexity = sum(1 for item in category_items if item.source == "Perplexity AI")
            cat_reddit = sum(1 for item in category_items if item.source and item.source.startswith("Reddit r/"))
            cat_newsapi = sum(1 for item in category_items if item.source and item.source.startswith("NewsAPI -"))
            cat_other = sum(1 for item in category_items if item.source not in ["Perplexity AI"] and not (item.source and item.source.startswith("Reddit r/")) and not (item.source and item.source.startswith("NewsAPI -")))
            
            categories_info.append({
                "id": cat.id,
                "category_name": cat.category_name,
                "short_summary": cat.short_summary,
                "created_at": to_utc_z(cat.created_at),
                "item_counts": {
                    "perplexity": cat_perplexity,
                    "reddit": cat_reddit,
                    "newsapi": cat_newsapi,
                    "other": cat_other,
                    "total": len(category_items)
                }
            })
        
        # Get recent items (last 10) for each source
        recent_perplexity = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.source == "Perplexity AI"
        ).order_by(FeedItemDB.created_at.desc()).limit(10).all()
        
        recent_reddit = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.source.like('Reddit r/%')
        ).order_by(FeedItemDB.created_at.desc()).limit(10).all()
        
        recent_newsapi = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.source.like('NewsAPI -%')
        ).order_by(FeedItemDB.created_at.desc()).limit(10).all()
        
        def format_recent_items(items):
            return [{
                "id": item.id,
                "title": item.title,
                "source": item.source,
                "category": item.category,
                "created_at": to_utc_z(item.created_at),
                "published_at": to_utc_z(item.published_at)
            } for item in items]
        
        return {
            "user_id": user_id,
            "total_categories": len(user_categories),
            "categories": categories_info,
            "feed_stats": {
                "perplexity": perplexity_count,
                "reddit": reddit_count,
                "newsapi": newsapi_count,
                "other": other_count,
                "total": total_count
            },
            "recent_items": {
                "perplexity": format_recent_items(recent_perplexity),
                "reddit": format_recent_items(recent_reddit),
                "newsapi": format_recent_items(recent_newsapi)
            },
            "generated_at": to_utc_z(datetime.utcnow())
        }
        
    except Exception as e:
        print(f"[ERROR] Debug user feed stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating feed stats: {str(e)}")
    finally:
        db.close()

@app.get("/debug/filtering-stats/{user_id}")
async def debug_filtering_stats(user_id: int):
    """Debug endpoint to show filtering statistics for a user's feed items"""
    
    db = SessionLocal()
    try:
        # Get user categories
        user_categories = db.query(UserCategoryDB).filter(UserCategoryDB.user_id == user_id).all()
        if not user_categories:
            raise HTTPException(status_code=404, detail="No categories found for user")
        
        # Get feed items for this user's categories
        category_names = [cat.category_name for cat in user_categories]
        feed_items = db.query(FeedItemDB).filter(FeedItemDB.category.in_(category_names)).all()
        
        total_items = len(feed_items)
        source_breakdown = {}
        category_breakdown = {}
        
        for item in feed_items:
            source = item.source or "Unknown"
            category = item.category
            
            # Initialize source breakdown
            if source not in source_breakdown:
                source_breakdown[source] = {
                    "total": 0,
                    "kept": 0,
                    "filtered": 0
                }
            source_breakdown[source]["total"] += 1
            if item.is_relevant:
                source_breakdown[source]["kept"] += 1
            else:
                source_breakdown[source]["filtered"] += 1
            
            # Initialize category breakdown
            if category not in category_breakdown:
                category_breakdown[category] = {
                    "total": 0,
                    "kept": 0,
                    "filtered": 0
                }
            category_breakdown[category]["total"] += 1
            if item.is_relevant:
                category_breakdown[category]["kept"] += 1
            else:
                category_breakdown[category]["filtered"] += 1
        
        # Calculate filtering rates
        for source in source_breakdown:
            total = source_breakdown[source]["total"]
            kept = source_breakdown[source]["kept"]
            filtered = source_breakdown[source]["filtered"]
            source_breakdown[source]["filtering_rate"] = round((filtered / total * 100) if total > 0 else 0, 1)
        
        for category in category_breakdown:
            total = category_breakdown[category]["total"]
            kept = category_breakdown[category]["kept"]
            filtered = category_breakdown[category]["filtered"]
            category_breakdown[category]["filtering_rate"] = round((filtered / total * 100) if total > 0 else 0, 1)
        
        # Calculate overall stats
        relevant_items = sum(1 for item in feed_items if item.is_relevant)
        irrelevant_items = sum(1 for item in feed_items if not item.is_relevant)
        
        return {
            "user_id": user_id,
            "filtering_stats": {
                "total_items_processed": total_items,
                "items_kept": relevant_items,
                "items_filtered_out": irrelevant_items,
                "filtering_rate": round((irrelevant_items / total_items * 100) if total_items > 0 else 0, 1)
            },
            "source_breakdown": source_breakdown,
            "category_breakdown": category_breakdown,
            "note": "Filtering stats are calculated based on items currently in database. Filtered items are not stored."
        }
        
    except Exception as e:
        print(f"[ERROR] Debug filtering stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting filtering stats: {str(e)}")
    finally:
        db.close()

@app.get("/debug/cleanup-status")
async def debug_cleanup_status():
    """Debug endpoint to check cleanup task status and configuration"""
    return {
        "cleanup_configuration": {
            "scheduled_task": "cleanup-old-feed-items",
            "frequency": "Every 3 hours",
            "retention_policy": "24 hours",
            "task_name": "runners.cleanup_runner.cleanup_old_feed_items"
        },
        "cleanup_features": {
            "automated_cleanup": True,
            "source_based_cleanup": True,
            "category_based_cleanup": True,
            "user_based_cleanup": True
        },
        "cleanup_sources": [
            "Perplexity AI",
            "NewsAPI",
            "Reddit",
            "Social Media"
        ],
        "note": "Currently running synchronously - Celery integration coming later"
    }

@app.get("/debug/cleanup-stats")
async def debug_cleanup_stats():
    """Debug endpoint to show actual cleanup statistics from the database"""
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta
        
        # Get current time
        now = datetime.utcnow()
        
        # Calculate time thresholds
        cutoff_24h = now - timedelta(hours=24)
        cutoff_48h = now - timedelta(hours=48)
        cutoff_7d = now - timedelta(days=7)
        
        # Count items by age
        items_24h_old = db.query(FeedItemDB).filter(FeedItemDB.created_at < cutoff_24h).count()
        items_48h_old = db.query(FeedItemDB).filter(FeedItemDB.created_at < cutoff_48h).count()
        items_7d_old = db.query(FeedItemDB).filter(FeedItemDB.created_at < cutoff_7d).count()
        total_items = db.query(FeedItemDB).count()
        
        # Count items by source
        source_counts = {}
        sources = db.query(FeedItemDB.source).distinct().all()
        for source in sources:
            if source[0]:
                source_counts[source[0]] = db.query(FeedItemDB).filter(FeedItemDB.source == source[0]).count()
        
        # Count items by relevance
        relevant_items = db.query(FeedItemDB).filter(FeedItemDB.is_relevant == True).count()
        irrelevant_items = db.query(FeedItemDB).filter(FeedItemDB.is_relevant == False).count()
        
        return {
            "current_time": now.isoformat(),
            "item_counts": {
                "total_items": total_items,
                "items_older_than_24h": items_24h_old,
                "items_older_than_48h": items_48h_old,
                "items_older_than_7d": items_7d_old
            },
            "relevance_counts": {
                "relevant_items": relevant_items,
                "irrelevant_items": irrelevant_items,
                "relevance_rate": round(relevant_items / total_items * 100, 1) if total_items > 0 else 0
            },
            "source_distribution": source_counts,
            "cleanup_recommendations": {
                "should_cleanup_24h": items_24h_old > 0,
                "should_cleanup_48h": items_48h_old > 0,
                "should_cleanup_7d": items_7d_old > 0
            }
        }
        
    except Exception as e:
        print(f"[ERROR] Cleanup stats error: {e}")
        return {"error": f"Failed to get cleanup stats: {str(e)}"}
    finally:
        db.close()

# AI Summary API Endpoints

@app.get("/ai-summary/status")
async def get_ai_summary_status_for_current_user(
    current_user: dict = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """Get the status of AI summary generation for the currently authenticated user"""
    try:
        user_id = current_user["id"]
        
        # Get user's active categories
        user_categories = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id,
            UserCategoryDB.is_active == True
        ).all()
        
        if not user_categories:
            return {
                "user_id": user_id,
                "status": "no_categories",
                "message": "User has no active categories",
                "can_generate_summary": False
            }
        
        # Get feed items for user's categories
        category_names = [cat.category_name for cat in user_categories]
        feed_items = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.is_relevant == True
        ).all()
        
        if not feed_items:
            return {
                "user_id": user_id,
                "status": "no_feed_items",
                "message": "No relevant feed items found",
                "can_generate_summary": False
            }
        
        # Check if we have enough recent items
        recent_items = [item for item in feed_items 
                       if item.published_at and 
                       (datetime.utcnow() - item.published_at).days <= 7]
        
        return {
            "user_id": user_id,
            "status": "ready",
            "message": "Ready to generate summary",
            "can_generate_summary": True,
            "total_categories": len(user_categories),
            "total_feed_items": len(feed_items),
            "recent_feed_items": len(recent_items),
            "categories": [cat.category_name for cat in user_categories],
            "last_updated": to_utc_z(max(item.updated_at for item in feed_items)) if feed_items else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to get AI summary status for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get AI summary status: {str(e)}"
        )
    finally:
        db.close()

# AI Summary Storage and Retrieval API
@app.post("/ai-summary/store")
async def store_ai_summary(
    summary_data: dict,
    current_user: dict = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """Store an AI-generated summary in the database"""
    try:
        user_id = current_user["id"]
        
        # Create new AI summary record
        ai_summary = AISummaryDB(
            user_id=user_id,
            summary_content=summary_data.get("summary", ""),
            word_count=summary_data.get("word_count", 0),
            max_words_requested=summary_data.get("max_words_requested", 300),
            categories_covered=summary_data.get("categories_covered", []),
            total_feed_items_analyzed=summary_data.get("total_feed_items_analyzed", 0),
            source=summary_data.get("source", "Perplexity AI")
        )
        
        db.add(ai_summary)
        db.commit()
        db.refresh(ai_summary)
        
        return {
            "message": "AI summary stored successfully",
            "summary_id": ai_summary.id,
            "user_id": user_id,
            "generated_at": ai_summary.generated_at.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to store AI summary for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to store AI summary: {str(e)}"
        )
    finally:
        db.close()

@app.get("/ai-summary/latest")
async def get_latest_ai_summary(
    current_user: dict = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """Get the latest AI summary for the current user"""
    try:
        user_id = current_user["id"]
        
        # Get the most recent active summary for this user
        latest_summary = db.query(AISummaryDB).filter(
            AISummaryDB.user_id == user_id,
            AISummaryDB.is_active == True
        ).order_by(AISummaryDB.generated_at.desc()).first()
        
        if not latest_summary:
            return {
                "user_id": user_id,
                "has_summary": False,
                "message": "No AI summary available for this user"
            }
        
        return {
            "user_id": user_id,
            "has_summary": True,
            "summary": {
                "id": latest_summary.id,
                "summary_content": latest_summary.summary_content,
                "word_count": latest_summary.word_count,
                "max_words_requested": latest_summary.max_words_requested,
                "categories_covered": latest_summary.categories_covered,
                "total_feed_items_analyzed": latest_summary.total_feed_items_analyzed,
                "generated_at": latest_summary.generated_at.isoformat(),
                "source": latest_summary.source
            }
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to get latest AI summary for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get latest AI summary: {str(e)}"
        )
    finally:
        db.close()

# Trigger AI summary generation when new feed items are added
def trigger_ai_summary_generation_for_user(user_id: int, db: Session):
    """Background function to generate AI summary when new feed items are added"""
    try:
        # Check if user has active categories and feed items
        user_categories = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id,
            UserCategoryDB.is_active == True
        ).all()
        
        if not user_categories:
            return
        
        category_names = [cat.category_name for cat in user_categories]
        feed_items = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.is_relevant == True
        ).all()
        
        if len(feed_items) < 5:  # Only generate if there are enough items
            return
        
        # Generate summary using existing logic
        # This will be called from the feed update functions
        
    except Exception as e:
        print(f"[ERROR] Failed to trigger AI summary generation for user {user_id}: {e}")

# Modified AI Summary Generation with Auto-Storage
@app.post("/ai-summary/generate-and-store")
async def generate_and_store_ai_summary(
    max_words: int = 300,
    current_user: dict = Depends(get_current_user),
    db: SessionLocal = Depends(get_db)
):
    """Generate an AI-assisted summary and store it in the database"""
    try:
        user_id = current_user["id"]
        print(f"[INFO] Starting AI summary generation for user {user_id} with max_words={max_words}")
        
        # Get user's active categories
        print(f"[DEBUG] Fetching active categories for user {user_id}")
        user_categories = db.query(UserCategoryDB).filter(
            UserCategoryDB.user_id == user_id,
            UserCategoryDB.is_active == True
        ).all()
        
        print(f"[DEBUG] Found {len(user_categories)} active categories for user {user_id}")
        
        if not user_categories:
            print(f"[ERROR] No active categories found for user {user_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"No active categories found for user {user_id}"
            )
        
        # Get feed items for user's categories (only relevant items)
        category_names = [cat.category_name for cat in user_categories]
        print(f"[DEBUG] Fetching feed items for categories: {category_names}")
        
        feed_items = db.query(FeedItemDB).filter(
            FeedItemDB.category.in_(category_names),
            FeedItemDB.is_relevant == True
        ).order_by(FeedItemDB.published_at.desc()).limit(100).all()
        
        print(f"[DEBUG] Found {len(feed_items)} relevant feed items for user {user_id}")
        
        if not feed_items:
            print(f"[ERROR] No relevant feed items found for user {user_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"No relevant feed items found for user {user_id}"
            )
        
        # Group feed items by category
        print(f"[DEBUG] Grouping feed items by category for user {user_id}")
        category_feed_data = {}
        for category in user_categories:
            category_items = [item for item in feed_items if item.category == category.category_name]
            if category_items:
                category_feed_data[category.category_name] = [
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "source": item.source,
                        "published_at": to_utc_z(item.published_at) if item.published_at else None,
                        "url": item.url
                    }
                    for item in category_items[:20]  # Limit to 20 items per category
                ]
        
        print(f"[DEBUG] Grouped feed items into {len(category_feed_data)} categories for user {user_id}")
        
        # Create the JSON structure for Perplexity
        feed_summary_data = {
            "user_categories": list(category_feed_data.keys()),
            "feed_items_by_category": category_feed_data
        }
        
        print(f"[DEBUG] Created feed summary data with {len(category_feed_data)} categories for user {user_id}")
        
        # Generate the prompt for Perplexity
        prompt = f"""Given this JSON structure that is organized by the topic category and news items on that category, generate a summarization for the user to read as a briefing. The summary should be up to {max_words} words long.

JSON Structure:
{json.dumps(feed_summary_data, indent=2)}

CRITICAL FORMATTING REQUIREMENTS - YOU MUST FOLLOW THESE EXACTLY:
1. Start each category with a NEW PARAGRAPH
2. Begin each category paragraph with "**CATEGORY NAME:**" in bold
3. Use double line breaks between categories
4. Keep each category focused on its specific topic
5. Make the summary scannable and easy to read

Example format:
**Category 1 Name:**
Content for category 1...

**Category 2 Name:**
Content for category 2...

Please provide a comprehensive yet concise summary that:
1. Highlights the most important developments across all categories
2. Identifies any emerging trends or patterns
3. Provides context for why these items matter
4. Is written in a professional briefing format
5. Stays within the {max_words} word limit

RESPOND WITH EXACT FORMATTING AS SHOWN IN THE EXAMPLE ABOVE."""
        
        print(f"[DEBUG] Generated prompt for user {user_id}, length: {len(prompt)} characters")
        
        # Call Perplexity API
        perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        if not perplexity_api_key:
            print(f"[ERROR] PERPLEXITY_API_KEY not configured for user {user_id}")
            raise HTTPException(
                status_code=500, 
                detail="PERPLEXITY_API_KEY not configured"
            )
        
        print(f"[DEBUG] Using Perplexity API key: {perplexity_api_key[:10]}... for user {user_id}")
        print(f"[DEBUG] API key length: {len(perplexity_api_key)} characters")
        print(f"[DEBUG] API key starts with: {perplexity_api_key[:20]}")
        print(f"[DEBUG] API key ends with: {perplexity_api_key[-10:]}")
        
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are an expert news analyst and briefing writer. Your task is to create concise, informative summaries of news items organized by category. Focus on clarity, relevance, and actionable insights. CRITICAL: Always structure your response with clear paragraph breaks between different categories. Start each category with a new paragraph and use bold formatting for category names (e.g., '**Category Name:**'). Make the summary easy to scan and read."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        print(f"[DEBUG] Making Perplexity API call for user {user_id}")
        perplexity_url = "https://api.perplexity.ai/chat/completions"
        print(f"[DEBUG] API URL: {perplexity_url}")
        print(f"[DEBUG] Request payload keys: {list(payload.keys())}")
        print(f"[DEBUG] Request payload model: {payload['model']}")
        print(f"[DEBUG] Request payload max_tokens: {payload['max_tokens']}")
        print(f"[DEBUG] Request payload temperature: {payload['temperature']}")
        print(f"[DEBUG] Number of messages: {len(payload['messages'])}")
        
        try:
            response = requests.post(perplexity_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            print(f"[DEBUG] Perplexity API response status: {response.status_code} for user {user_id}")
            
            result = response.json()
            print(f"[DEBUG] Perplexity API response structure: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'} for user {user_id}")
            
            if "choices" not in result or not result["choices"]:
                print(f"[ERROR] Invalid Perplexity API response for user {user_id}: {result}")
                raise HTTPException(
                    status_code=500, 
                    detail="Invalid response from Perplexity API"
                )
            
            summary_content = result["choices"][0]["message"]["content"]
            print(f"[DEBUG] Received summary content for user {user_id}, length: {len(summary_content)} characters")
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Perplexity API request failed for user {user_id}: {e}")
            error_content = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_content = e.response.text
                except:
                    error_content = str(e)
            print(f"[ERROR] Full error response: {error_content}")
            raise HTTPException(
                status_code=500, 
                detail=f"Perplexity API error: {str(e)}"
            )
        
        # Post-process the summary to ensure proper formatting
        # Split by categories and reformat if needed
        try:
            categories = list(category_feed_data.keys())
            if len(categories) > 1:
                print(f"[DEBUG] Post-processing summary for {len(categories)} categories: {categories}")
                # Clean up any duplicate or malformed category headers
                summary_content = summary_content.replace("** **", "**")  # Fix double asterisks
                summary_content = summary_content.replace("**: **", ":**")  # Fix malformed headers
                
                # Remove duplicate category headers
                for category in categories:
                    # Find all instances of this category header
                    header_pattern = f"**{category}:**"
                    if summary_content.count(header_pattern) > 1:
                        print(f"[DEBUG] Found duplicate headers for category: {category}")
                        # Keep only the first occurrence
                        first_pos = summary_content.find(header_pattern)
                        if first_pos != -1:
                            # Remove subsequent occurrences
                            remaining_content = summary_content[first_pos + len(header_pattern):]
                            # Find next category header or end
                            next_header_pos = -1
                            for other_cat in categories:
                                if other_cat != category:
                                    other_header = f"**{other_cat}:**"
                                    pos = remaining_content.find(other_header)
                                    if pos != -1 and (next_header_pos == -1 or pos < next_header_pos):
                                        next_header_pos = pos
                            
                            if next_header_pos != -1:
                                # Keep content up to next category
                                summary_content = summary_content[:first_pos + len(header_pattern)] + remaining_content[:next_header_pos]
                            else:
                                # Keep content up to end
                                summary_content = summary_content[:first_pos + len(header_pattern)] + remaining_content
                
                # Ensure proper spacing between categories
                for category in categories:
                    header_pattern = f"**{category}:**"
                    if header_pattern in summary_content:
                        # Ensure there's a newline before each category header (except the first)
                        if not summary_content.startswith(header_pattern):
                            summary_content = summary_content.replace(header_pattern, f"\n\n{header_pattern}")
                            # Remove any double newlines
                            summary_content = summary_content.replace("\n\n\n", "\n\n")
                
                print(f"[DEBUG] Post-processing completed. Summary length: {len(summary_content)} characters")
        except Exception as e:
            print(f"[ERROR] Post-processing failed for user {user_id}: {e}")
            # Continue with original content if post-processing fails
        
        # Count actual words in the summary
        actual_word_count = len(summary_content.split())
        print(f"[DEBUG] Summary word count for user {user_id}: {actual_word_count} words")
        
        # Store the summary in the database
        print(f"[DEBUG] Storing AI summary in database for user {user_id}")
        ai_summary = AISummaryDB(
            user_id=user_id,
            summary_content=summary_content,
            word_count=actual_word_count,
            max_words_requested=max_words,
            categories_covered=list(category_feed_data.keys()),
            total_feed_items_analyzed=len(feed_items),
            source="Perplexity AI"
        )
        
        db.add(ai_summary)
        db.commit()
        db.refresh(ai_summary)
        print(f"[INFO] Successfully stored AI summary with ID {ai_summary.id} for user {user_id}")
        
        return {
            "message": "AI summary generated and stored successfully",
            "summary_id": ai_summary.id,
            "user_id": user_id,
            "summary": summary_content,
            "word_count": actual_word_count,
            "max_words_requested": max_words,
            "categories_covered": list(category_feed_data.keys()),
            "total_feed_items_analyzed": len(feed_items),
            "generated_at": ai_summary.generated_at.isoformat(),
            "source": "Perplexity AI"
        }
        
    except HTTPException:
        print(f"[ERROR] HTTPException raised for user {current_user['id']}")
        raise
    except Exception as e:
        print(f"[ERROR] Failed to generate and store AI summary for user {current_user['id']}: {e}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate and store AI summary: {str(e)}"
        )
    finally:
        print(f"[DEBUG] Closing database connection for user {current_user['id']}")
        db.close()

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 