# AI Summary API Documentation

## Overview

The AI Summary API provides intelligent summarization of user feed items using Perplexity AI. It analyzes feed items organized by category and generates comprehensive, professional briefings that highlight key developments and trends.

## Features

- **Intelligent Summarization**: Uses Perplexity AI to analyze and summarize feed items
- **Category-based Organization**: Groups feed items by user categories for better context
- **Configurable Length**: Adjustable word count (default: 300 words)
- **Background Processing**: Support for asynchronous summary generation via Celery
- **Status Checking**: Endpoints to check if summaries can be generated

## API Endpoints

### 1. Generate AI Summary (Synchronous)

**POST** `/ai-summary/generate/{user_id}`

Generates an AI summary immediately. This endpoint may take some time to complete as it waits for the Perplexity API response.

#### Parameters

- `user_id` (path): The ID of the user to generate a summary for
- `max_words` (query, optional): Maximum word count for the summary (default: 300)

#### Response

```json
{
  "user_id": 1,
  "summary": "Your AI-generated summary content here...",
  "word_count": 285,
  "max_words_requested": 300,
  "categories_covered": ["Technology", "Business", "Science"],
  "total_feed_items_analyzed": 45,
  "generated_at": "2024-01-15T10:30:00Z",
  "source": "Perplexity AI"
}
```

### 2. Generate AI Summary (Background)

**POST** `/ai-summary/generate-background/{user_id}`

Starts background summary generation using Celery. Returns immediately with a task ID.

#### Parameters

- `user_id` (path): The ID of the user to generate a summary for
- `max_words` (query, optional): Maximum word count for the summary (default: 300)

#### Response

```json
{
  "message": "AI summary generation started for user 1",
  "task_id": "abc123-def456-ghi789",
  "status": "pending",
  "user_id": 1,
  "max_words": 300
}
```

### 3. Check Summary Status

**GET** `/ai-summary/status/{user_id}`

Checks if a user can generate a summary and provides status information.

#### Parameters

- `user_id` (path): The ID of the user to check

#### Response

```json
{
  "user_id": 1,
  "status": "ready",
  "message": "Ready to generate summary",
  "can_generate_summary": true,
  "total_categories": 3,
  "total_feed_items": 45,
  "recent_feed_items": 23,
  "categories": ["Technology", "Business", "Science"],
  "last_updated": "2024-01-15T10:25:00Z"
}
```

### 4. Check Task Status

**GET** `/task/{task_id}`

Check the status of a background task (including AI summary generation).

#### Parameters

- `task_id` (path): The task ID returned from background generation

#### Response

```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "SUCCESS",
  "result": {
    "status": "success",
    "user_id": 1,
    "summary": "Your AI-generated summary content here...",
    "word_count": 285,
    "generated_at": "2024-01-15T10:30:00Z"
  }
}
```

## How It Works

### 1. Data Collection
The API collects:
- User's active categories
- Relevant feed items for those categories (limited to 100 most recent)
- Item metadata (title, summary, source, URL, publication date)

### 2. Data Organization
Feed items are organized by category into a structured JSON format:

```json
{
  "user_categories": ["Technology", "Business"],
  "feed_items_by_category": {
    "Technology": [
      {
        "title": "AI Breakthrough in Machine Learning",
        "summary": "Researchers discover new algorithm...",
        "source": "TechCrunch",
        "published_at": "2024-01-15T10:00:00Z",
        "url": "https://example.com/article1"
      }
    ],
    "Business": [
      {
        "title": "Market Trends in Q4 2024",
        "summary": "Economic indicators show...",
        "source": "Bloomberg",
        "published_at": "2024-01-15T09:30:00Z",
        "url": "https://example.com/article2"
      }
    ]
  }
}
```

### 3. AI Processing
The structured data is sent to Perplexity AI with a prompt that:
- Requests a professional briefing format
- Specifies the word limit
- Asks for comprehensive coverage across categories
- Emphasizes identifying trends and providing context

### 4. Response Processing
The API:
- Extracts the generated summary
- Counts actual words
- Returns structured response with metadata

## Usage Examples

### Frontend Integration

```javascript
// Check if user can generate summary
const statusResponse = await fetch(`/ai-summary/status/${userId}`);
const status = await statusResponse.json();

if (status.can_generate_summary) {
  // Trigger background generation
  const generateResponse = await fetch(`/ai-summary/generate-background/${userId}`, {
    method: 'POST'
  });
  const generateData = await generateResponse.json();
  
  // Poll for completion
  const taskId = generateData.task_id;
  const checkStatus = async () => {
    const taskResponse = await fetch(`/task/${taskId}`);
    const taskData = await taskResponse.json();
    
    if (taskData.status === 'SUCCESS') {
      // Display summary
      displaySummary(taskData.result.summary);
    } else if (taskData.status === 'PENDING') {
      // Continue polling
      setTimeout(checkStatus, 2000);
    }
  };
  
  checkStatus();
}
```

### Direct Generation

```javascript
// Generate summary immediately (may take longer)
const response = await fetch(`/ai-summary/generate/${userId}?max_words=500`, {
  method: 'POST'
});
const data = await response.json();

if (response.ok) {
  displaySummary(data.summary);
}
```

## Configuration

### Environment Variables

- `PERPLEXITY_API_KEY`: Required API key for Perplexity AI

### Perplexity API Settings

- **Model**: `sonar` (optimized for summarization)
- **Max Tokens**: 1000 (sufficient for 300-word summaries)
- **Temperature**: 0.3 (balanced creativity and consistency)
- **Timeout**: 30 seconds

## Error Handling

The API handles various error scenarios:

- **No Categories**: User has no active categories
- **No Feed Items**: No relevant feed items found
- **API Errors**: Perplexity API failures
- **Database Errors**: Database connection or query issues

All errors return appropriate HTTP status codes and descriptive error messages.

## Performance Considerations

- **Feed Item Limit**: Maximum 100 items analyzed per summary
- **Category Item Limit**: Maximum 20 items per category
- **Caching**: Consider implementing response caching for repeated requests
- **Background Processing**: Use background generation for better user experience

## Future Enhancements

- **Summary Caching**: Store generated summaries to avoid regeneration
- **User Preferences**: Allow users to customize summary style and focus areas
- **Scheduled Generation**: Automatically generate summaries at regular intervals
- **Multi-language Support**: Generate summaries in user's preferred language
- **Summary History**: Track and display previously generated summaries
