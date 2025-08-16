// Frontend Integration Example for AI Summary API
// This shows how to integrate the AI summary generation when a user logs in

class AISummaryManager {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
        this.currentUserId = null;
        this.summaryCache = new Map();
    }

    // Set the current user ID after login
    setCurrentUser(userId) {
        this.currentUserId = userId;
        console.log(`AI Summary Manager: User ID set to ${userId}`);
    }

    // Check if user can generate summary
    async checkSummaryStatus() {
        if (!this.currentUserId) {
            throw new Error('No user ID set. Please login first.');
        }

        try {
            const response = await fetch(`${this.baseUrl}/ai-summary/status/${this.currentUserId}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error checking summary status:', error);
            throw error;
        }
    }

    // Generate summary in background (recommended for login flow)
    async generateSummaryBackground(maxWords = 300) {
        if (!this.currentUserId) {
            throw new Error('No user ID set. Please login first.');
        }

        try {
            const response = await fetch(`${this.baseUrl}/ai-summary/generate-background/${this.currentUserId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error starting background summary generation:', error);
            throw error;
        }
    }

    // Poll for task completion
    async pollTaskCompletion(taskId, onProgress = null, maxAttempts = 30) {
        let attempts = 0;
        
        const poll = async () => {
            try {
                const response = await fetch(`${this.baseUrl}/task/${taskId}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const taskData = await response.json();
                
                if (onProgress) {
                    onProgress(taskData);
                }

                if (taskData.status === 'SUCCESS') {
                    // Cache the summary
                    if (taskData.result && taskData.result.summary) {
                        this.summaryCache.set(this.currentUserId, {
                            summary: taskData.result.summary,
                            wordCount: taskData.result.word_count,
                            generatedAt: taskData.result.generated_at,
                            categories: taskData.result.categories_covered
                        });
                    }
                    return taskData.result;
                } else if (taskData.status === 'FAILURE') {
                    throw new Error(`Task failed: ${taskData.error || 'Unknown error'}`);
                } else if (attempts >= maxAttempts) {
                    throw new Error('Task timed out');
                } else {
                    // Continue polling
                    attempts++;
                    setTimeout(poll, 2000); // Poll every 2 seconds
                }
            } catch (error) {
                console.error('Error polling task status:', error);
                throw error;
            }
        };

        return poll();
    }

    // Get cached summary if available
    getCachedSummary() {
        if (!this.currentUserId) return null;
        return this.summaryCache.get(this.currentUserId);
    }

    // Clear cache for current user
    clearCache() {
        if (this.currentUserId) {
            this.summaryCache.delete(this.currentUserId);
        }
    }
}

// Example usage in a login flow
class LoginFlow {
    constructor() {
        this.summaryManager = new AISummaryManager('http://localhost:8001');
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Login form submission
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        // Summary generation button
        const generateSummaryBtn = document.getElementById('generateSummaryBtn');
        if (generateSummaryBtn) {
            generateSummaryBtn.addEventListener('click', () => this.handleGenerateSummary());
        }
    }

    async handleLogin(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        const username = formData.get('username');
        const password = formData.get('password');

        try {
            // Simulate login API call
            const userId = await this.performLogin(username, password);
            
            if (userId) {
                // Set user ID in summary manager
                this.summaryManager.setCurrentUser(userId);
                
                // Show success message
                this.showMessage('Login successful!', 'success');
                
                // Check if user can generate summary
                await this.checkSummaryCapability();
                
                // Automatically start summary generation
                await this.startSummaryGeneration();
            }
        } catch (error) {
            this.showMessage(`Login failed: ${error.message}`, 'error');
        }
    }

    async performLogin(username, password) {
        // This would be your actual login API call
        // For demo purposes, we'll simulate a successful login
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve(1); // Return user ID 1
            }, 1000);
        });
    }

    async checkSummaryCapability() {
        try {
            const status = await this.summaryManager.checkSummaryStatus();
            
            if (status.can_generate_summary) {
                this.showMessage(`Ready to generate summary. Found ${status.total_feed_items} feed items across ${status.total_categories} categories.`, 'info');
            } else {
                this.showMessage(`Cannot generate summary: ${status.message}`, 'warning');
            }
        } catch (error) {
            this.showMessage(`Error checking summary capability: ${error.message}`, 'error');
        }
    }

    async startSummaryGeneration() {
        try {
            this.showMessage('Starting AI summary generation...', 'info');
            
            // Start background generation
            const taskData = await this.summaryManager.generateSummaryBackground(300);
            
            if (taskData.task_id) {
                this.showMessage(`Summary generation started. Task ID: ${taskData.task_id}`, 'info');
                
                // Poll for completion
                const result = await this.summaryManager.pollTaskCompletion(
                    taskData.task_id,
                    (progress) => {
                        this.showMessage(`Generating summary... Status: ${progress.status}`, 'info');
                    }
                );
                
                if (result) {
                    this.showMessage('Summary generated successfully!', 'success');
                    this.displaySummary(result);
                }
            }
        } catch (error) {
            this.showMessage(`Error generating summary: ${error.message}`, 'error');
        }
    }

    async handleGenerateSummary() {
        // Check if we have a cached summary
        const cached = this.summaryManager.getCachedSummary();
        
        if (cached) {
            this.showMessage('Displaying cached summary', 'info');
            this.displaySummary(cached);
        } else {
            // Generate new summary
            await this.startSummaryGeneration();
        }
    }

    displaySummary(summaryData) {
        const summaryContainer = document.getElementById('summaryContainer');
        if (summaryContainer) {
            summaryContainer.innerHTML = `
                <div class="summary-header">
                    <h3>AI-Generated Summary</h3>
                    <div class="summary-meta">
                        <span class="word-count">${summaryData.wordCount} words</span>
                        <span class="categories">Categories: ${summaryData.categories?.join(', ') || 'N/A'}</span>
                        <span class="generated-at">Generated: ${new Date(summaryData.generatedAt).toLocaleString()}</span>
                    </div>
                </div>
                <div class="summary-content">
                    ${summaryData.summary}
                </div>
            `;
            summaryContainer.style.display = 'block';
        }
    }

    showMessage(message, type = 'info') {
        const messageContainer = document.getElementById('messageContainer');
        if (messageContainer) {
            messageContainer.innerHTML = `
                <div class="message message-${type}">
                    ${message}
                </div>
            `;
            messageContainer.style.display = 'block';
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                messageContainer.style.display = 'none';
            }, 5000);
        }
    }
}

// Initialize the login flow when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new LoginFlow();
});

// Example HTML structure this would work with:
/*
<!DOCTYPE html>
<html>
<head>
    <title>AI Summary Demo</title>
    <style>
        .message { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .message-success { background-color: #d4edda; color: #155724; }
        .message-error { background-color: #f8d7da; color: #721c24; }
        .message-info { background-color: #d1ecf1; color: #0c5460; }
        .message-warning { background-color: #fff3cd; color: #856404; }
        .summary-header { margin-bottom: 15px; }
        .summary-meta { font-size: 0.9em; color: #666; }
        .summary-meta span { margin-right: 15px; }
        .summary-content { line-height: 1.6; }
    </style>
</head>
<body>
    <div id="messageContainer"></div>
    
    <form id="loginForm">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>
    
    <button id="generateSummaryBtn" style="display: none;">Generate Summary</button>
    
    <div id="summaryContainer" style="display: none;"></div>
</body>
</html>
*/
