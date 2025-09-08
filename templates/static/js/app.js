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
    const username = document.getElementById('signup-username').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = document.getElementById('signup-password').value;
    
    // Frontend validation
    if (!username || username.length < 3) {
        showError('Username must be at least 3 characters long.');
        return;
    }
    if (username.length > 50) {
        showError('Username must be less than 50 characters.');
        return;
    }
    if (!email || !email.includes('@')) {
        showError('Please enter a valid email address.');
        return;
    }
    if (!password || password.length < 8) {
        showError('Password must be at least 8 characters long.');
        return;
    }
    
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
            // Signup successful, now automatically log the user in
            showSuccess('Account created successfully! Logging you in...');
            
            // Auto-login after successful signup
            try {
                const loginResponse = await fetch('/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });
                
                if (loginResponse.ok) {
                    const loginData = await loginResponse.json();
                    localStorage.setItem('token', loginData.access_token);
                    showFeed();
                    startPeriodicFeedRefresh();
                } else {
                    showError('Account created but login failed. Please try logging in manually.');
                }
            } catch (loginError) {
                showError('Account created but login failed. Please try logging in manually.');
            }
        } else {
            showError(data.detail || 'Signup failed. Please try again.');
        }
    } catch (error) {
        showError('Signup failed. Please try again.');
    }
}

let currentOffset = 0;
const FEED_LIMIT = 30;
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
        console.log(`[DEBUG] Reddit item data: title='${item.title}', content='${item.content}', source='${item.source}'`);
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
                    <div class="reddit-title">${escapeHtml(item.title || 'No title available')}</div>
                    ${item.content ? `<div class="reddit-top-comment"><span style='color:#888;font-size:0.95em;'>Top comment:</span> ${escapeHtml(item.content)}</div>` : ''}
                    ${!item.title && !item.content ? `<div style="color: #666; font-style: italic;">No content available</div>` : ''}
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

// AI Summary Functions
let aiSummaryCollapsed = false;

async function loadAISummary() {
    console.log('loadAISummary called');
    const token = localStorage.getItem('token');
    console.log('Token found:', !!token);
    if (!token) {
        console.log('No token, returning early');
        return;
    }

    try {
        console.log('Showing banner...');
        // Show the banner first
        document.getElementById('ai-summary-banner').style.display = 'block';
        console.log('Banner should now be visible');
        
        // Try to get existing summary
        console.log('Fetching latest summary...');
        const response = await fetch('/ai-summary/latest', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        console.log('Response status:', response.status);
        
        if (response.ok) {
            const data = await response.json();
            console.log('Response data:', data);
            if (data.has_summary) {
                console.log('Displaying existing summary');
                displayAISummary(data.summary);
            } else {
                console.log('No existing summary, generating new one');
                // No existing summary, generate one
                await generateAISummary();
            }
        } else {
            console.log('Error response, generating new summary');
            // Error getting summary, generate new one
            await generateAISummary();
        }
    } catch (error) {
        console.error('Error loading AI summary:', error);
        // Show error state but keep banner visible
        document.getElementById('ai-summary-status').textContent = 'Error loading summary';
    }
}

async function generateAISummary() {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
        // Show loading state
        document.getElementById('ai-summary-loading').style.display = 'block';
        document.getElementById('ai-summary-text').style.display = 'none';
        document.getElementById('ai-summary-meta').style.display = 'none';
        document.getElementById('ai-summary-status').textContent = 'Generating...';

        const response = await fetch('/ai-summary/generate-and-store', {
            method: 'POST',
            headers: { 
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            displayAISummary(data);
            document.getElementById('ai-summary-status').textContent = 'Generated just now';
        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to generate summary');
        }
    } catch (error) {
        console.error('Error generating AI summary:', error);
        document.getElementById('ai-summary-status').textContent = 'Generation failed';
        document.getElementById('ai-summary-loading').style.display = 'none';
    }
}

function displayAISummary(summaryData) {
    // Hide loading
    document.getElementById('ai-summary-loading').style.display = 'none';
    
    // Show summary content
    const summaryText = document.getElementById('ai-summary-text');
    summaryText.style.display = 'block';
    
    // Process the summary content to handle line breaks properly
    let content = summaryData.summary_content || summaryData.summary;
    
    // Convert newlines to <br> tags for proper HTML line breaks
    // Using String.fromCharCode(10) to avoid escape sequence issues
    const newlineChar = String.fromCharCode(10);
    content = content.split(newlineChar).join('<br>');
    
    // Ensure double line breaks between categories for better readability
    content = content.split('<br><br>').join('<br><br><br>');
    
    // Escape HTML to prevent XSS, but preserve <br> tags
    content = escapeHtml(content);
    
    // Restore <br> tags after escaping
    content = content.split('&lt;br&gt;').join('<br>');
    
    summaryText.innerHTML = content;
    
    // Show meta information
    const metaDiv = document.getElementById('ai-summary-meta');
    metaDiv.style.display = 'block';
    
    document.getElementById('ai-summary-categories').textContent = 
        (summaryData.categories_covered || []).join(', ') || 'All categories';
    document.getElementById('ai-summary-words').textContent = 
        summaryData.word_count || 'Unknown';
    document.getElementById('ai-summary-time').textContent = 
        formatTime(summaryData.generated_at);
    document.getElementById('ai-summary-source').textContent = 
        summaryData.source || 'Perplexity AI';
}

function toggleAISummary() {
    const content = document.getElementById('ai-summary-content');
    const toggleBtn = document.getElementById('ai-summary-toggle');
    
    if (aiSummaryCollapsed) {
        content.classList.remove('collapsed');
        toggleBtn.textContent = 'Collapse';
        aiSummaryCollapsed = false;
    } else {
        content.classList.add('collapsed');
        toggleBtn.textContent = 'Expand';
        aiSummaryCollapsed = true;
    }
}

async function refreshAISummary() {
    await generateAISummary();
}

function formatTime(isoString) {
    if (!isoString) return 'Unknown';
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    } catch (e) {
        return 'Unknown';
    }
}

// Store the original showFeed function before overriding
const originalShowFeed = showFeed;

// Override showFeed to also load AI summary
showFeed = async function(offset = 0, categoryFilter = null) {
    console.log('Modified showFeed called with offset:', offset, 'categoryFilter:', categoryFilter);
    await originalShowFeed(offset, categoryFilter);
    console.log('Original showFeed completed, now loading AI summary...');
    // Load AI summary after feed is loaded
    await loadAISummary();
    console.log('AI summary loading completed');
};
