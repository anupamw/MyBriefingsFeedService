# AI Agent Roadmap for My Briefings Feed Service

## Current System Overview

### Existing Architecture
- **FastAPI backend** with PostgreSQL database
- **Multiple data sources**: Perplexity AI, Reddit, Social media
- **User categories**: Personalized interests per user (max 5 categories)
- **Celery tasks**: Background processing with PostgreSQL as broker
- **Frontend**: Modern web interface with real-time updates
- **Deployment**: GitHub Actions to droplet

### Recent Improvements
- Enhanced Reddit card display to show post content
- Fixed HTML parsing for Reddit RSS feeds
- Improved frontend styling and user experience
- Added category filtering and pagination

## AI Agent Vision

### Core Requirements
1. **Multi-source curation** from various news and social platforms
2. **Intelligent source selection** based on user categories
3. **Content relevance scoring** using ML algorithms
4. **Personalized feed generation** per user
5. **Continuous learning** from user engagement
6. **Memory system** for long-term adaptation

## Technical Architecture

### 1. Enhanced Data Sources
```python
# Planned additional sources
- News APIs (NewsAPI, GNews, Reuters)
- RSS feeds (BBC, TechCrunch, HackerNews)
- Twitter API integration
- YouTube trending
- GitHub trending
- Podcast transcripts
```

### 2. AI-Powered Curation Engine
```python
class FeedCurationAgent:
    def __init__(self):
        self.sources = {
            'perplexity': PerplexityRunner(),
            'reddit': RedditRunner(), 
            'news': NewsAPIRunner(),
            'twitter': TwitterRunner(),
            'hackernews': HackerNewsRunner(),
            'tech_crunch': RSSRunner('techcrunch'),
            'bbc': RSSRunner('bbc'),
            'reuters': RSSRunner('reuters')
        }
        self.curation_engine = CurationEngine()
```

### 3. Intelligent Source Selection
```python
class SourceSelector:
    def select_sources_for_user(self, user_id: int, category: str) -> List[str]:
        # AI determines which sources are most relevant for this category
        # e.g., "AI news" -> [perplexity, tech_crunch, hackernews]
        # e.g., "politics" -> [bbc, reuters, reddit]
```

### 4. Content Relevance Scoring
```python
class ContentScorer:
    def score_content(self, item: FeedItem, user_profile: UserProfile) -> float:
        # AI scores content relevance based on:
        # - User's historical engagement
        # - Content similarity to user's interests
        # - Source credibility
        # - Content freshness
        # - Diversity balance
```

## Engagement Tracking System

### Frontend Tracking
```javascript
class EngagementTracker {
    trackItemView(itemId)
    trackTimeSpent(itemId)
    trackInteraction(itemId, action, value)
    sendEngagementData()
}
```

### Backend Models
```python
class UserEngagementDB(Base):
    __tablename__ = "user_engagement"
    user_id = Column(Integer, ForeignKey("users.id"))
    feed_item_id = Column(Integer, ForeignKey("feed_items.id"))
    action_type = Column(String(50))  # 'view', 'click', 'expand', 'share', 'time_spent'
    engagement_value = Column(Float)
    metadata = Column(JSON)
```

### Engagement Score Calculation
```python
def calculate_engagement_score(summary: UserEngagementSummaryDB) -> float:
    score = 0.0
    score += summary.total_views * 0.1
    score += summary.total_clicks * 1.0
    score += min(summary.total_time_spent / 30.0, 5.0)
    return score
```

## Memory System Architecture

### Memory Types
1. **Short-term Memory**: Recent interactions and session context
2. **Long-term Memory**: User profiles and persistent preferences
3. **Episodic Memory**: Significant events for pattern recognition

### Memory Models
```python
class UserMemoryDB(Base):
    __tablename__ = "user_memory"
    user_id = Column(Integer, ForeignKey("users.id"))
    memory_type = Column(String(50))  # 'preference', 'behavior', 'context'
    memory_key = Column(String(100))
    memory_value = Column(JSON)
    confidence_score = Column(Float, default=1.0)

class UserBehaviorPatternDB(Base):
    __tablename__ = "user_behavior_patterns"
    user_id = Column(Integer, ForeignKey("users.id"))
    pattern_type = Column(String(50))  # 'reading_time', 'category_switching'
    pattern_data = Column(JSON)
    frequency = Column(Integer, default=1)
```

### Memory-Enhanced Curation
```python
class MemoryAwareCurationEngine:
    def curate_with_memory(self, user_id: int, limit: int = 20) -> List[FeedItem]:
        user_context = self.memory.get_user_context(user_id)
        candidate_items = self.get_candidate_items(user_id)
        scored_items = [(item, self.score_with_memory(item, user_context)) 
                       for item in candidate_items]
        return [item for item, score in sorted(scored_items, key=lambda x: x[1], reverse=True)[:limit]]
```

## Implementation Roadmap

### Phase 1: Enhanced Data Sources (Next Priority)
- [ ] Add NewsAPI integration
- [ ] Add RSS feed runners (BBC, TechCrunch, etc.)
- [ ] Add Twitter API integration
- [ ] Add HackerNews API
- [ ] Test and optimize source reliability

### Phase 2: AI Curation Engine
- [ ] Build intelligent source selector
- [ ] Implement content relevance scoring
- [ ] Create personalized curation engine
- [ ] Add diversity and balance algorithms
- [ ] Integrate with existing feed system

### Phase 3: Engagement Tracking
- [ ] Implement frontend tracking
- [ ] Create engagement database models
- [ ] Build engagement scoring system
- [ ] Add engagement analytics API
- [ ] Integrate with curation engine

### Phase 4: Memory System
- [ ] Implement memory storage models
- [ ] Build memory management system
- [ ] Create learning algorithms
- [ ] Add memory-enhanced curation
- [ ] Implement continuous adaptation

## Key Features

### Multi-Source Intelligence
- Automatically selects best sources for each user category
- Balances between different content types (news, social, AI-generated)

### Personalized Ranking
- Uses ML to rank content based on user preferences
- Considers content freshness, source credibility, and diversity

### Continuous Learning
- Tracks user engagement to improve future curation
- Adapts to changing user interests over time

### Diversity & Balance
- Ensures feed isn't dominated by one source or topic
- Maintains healthy mix of content types and perspectives

### Real-time Updates
- Background curation keeps feeds fresh
- Users get new content as it becomes available

## Technical Notes

### Project Structure
- Runner code should be in `services/feed-ingestion/runners/` directory
- Use project's built-in debug API for testing
- Celery configured with PostgreSQL (not Redis)
- GitHub Actions for deployment

### Database Considerations
- All new models should follow existing patterns
- Use proper indexing for performance
- Consider data retention policies for engagement data

### API Design
- Follow existing REST patterns
- Add proper authentication and authorization
- Include comprehensive error handling
- Add rate limiting for new endpoints

## Success Metrics

### User Engagement
- Time spent reading feeds
- Click-through rates
- Category switching patterns
- Return user frequency

### Content Quality
- Relevance scores
- Source diversity
- Content freshness
- User satisfaction ratings

### System Performance
- Feed generation speed
- API response times
- Database query optimization
- Scalability metrics

---

**Last Updated**: December 2024
**Status**: Phase 1 - Enhanced Data Sources (Next Priority)
**Current Focus**: Adding more news sources and RSS feeds 