// JavaScript for the index.html page

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const queryInput = document.getElementById('query');
    const submitButton = document.getElementById('submit-btn');
    const resultsContent = document.getElementById('output');
    const loadingIndicator = document.getElementById('loading-indicator');
    const successIndicator = document.getElementById('success-indicator');
    const errorIndicator = document.getElementById('error-indicator');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const viewReportButton = document.getElementById('view-report-button');
    const recentReportsList = document.getElementById('recent-reports-list');
    
    // Global variables
    let eventSource = null;
    let currentReportId = null;
    
    // Make setExampleQuery available globally
    window.setExampleQuery = function(query) {
        if (queryInput) {
            queryInput.value = query;
            // Optional: Auto-submit the query
            if (submitButton) {
                submitButton.click();
            }
        }
    };
    
    // Check for return from report page
    const isReturningFromReport = localStorage.getItem('returningFromReport') === 'true';
    if (isReturningFromReport) {
        // Restore previous HTML content and scroll position
        const savedHtml = localStorage.getItem('resultsContentHtml');
        const savedScrollPosition = localStorage.getItem('resultsContentScrollPosition');
        
        if (savedHtml) {
            resultsContent.innerHTML = savedHtml;
            
            // Restore report ID if available
            currentReportId = localStorage.getItem('currentReportId');
            
            // Show success and view report button if we have a report ID
            if (currentReportId) {
                if (successIndicator) successIndicator.classList.remove('hidden');
                if (viewReportButton) viewReportButton.classList.remove('hidden');
            }
            
            // Restore scroll position after a short delay to ensure content is rendered
            setTimeout(() => {
                if (savedScrollPosition) {
                    resultsContent.scrollTop = parseInt(savedScrollPosition);
                }
            }, 100);
        }
        
        // Clear the flag and saved data
        localStorage.removeItem('returningFromReport');
        localStorage.removeItem('resultsContentHtml');
        localStorage.removeItem('resultsContentScrollPosition');
    } else {
        // Only load recent reports if not returning from report page
        loadRecentReports();
    }
    
    // Event Listeners
    if (submitButton) {
        submitButton.addEventListener('click', handleFormSubmit);
    }
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
    
    if (viewReportButton) {
        viewReportButton.addEventListener('click', () => {
            // Save current state before navigating
            localStorage.setItem('resultsContentHtml', resultsContent.innerHTML);
            localStorage.setItem('resultsContentScrollPosition', resultsContent.scrollTop.toString());
            localStorage.setItem('returningFromReport', 'true');
            localStorage.setItem('currentReportId', currentReportId);
            
            // Navigate to report page
            window.location.href = `/report?report_id=${currentReportId}`;
        });
    }
    
    // Functions
    async function handleFormSubmit(event) {
        if (event) event.preventDefault();
        
        const query = queryInput.value.trim();
        if (!query) return;
        
        // Reset UI state
        resetUI();
        appendSystemMessage(`Processing query: "${query}"`);
        
        try {
            // Post the query to the API
            const response = await fetch('/api/run-workflow', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request: { query },
                    config: {
                        // Default config values
                        researcher_credits: 6,
                        market_credits: 6,
                        coder_credits: 0,
                        browser_credits: 3
                    }
                })
            });
            
            if (!response.ok) {
                throw new Error(`API request failed with status ${response.status}`);
            }
            
            const data = await response.json();
            const streamUrl = response.headers.get('Content-Location');
            
            if (!streamUrl) {
                throw new Error('No stream URL provided in response');
            }
            
            // Connect to the event stream
            connectToEventStream(streamUrl);
            
        } catch (error) {
            handleError(error);
        }
    }
    
    function connectToEventStream(streamUrl) {
        // Close any existing connection
        if (eventSource) {
            eventSource.close();
        }
        
        // Create a new EventSource connection
        eventSource = new EventSource(streamUrl);
        
        // Set up event handlers
        eventSource.onmessage = handleEventMessage;
        eventSource.onerror = handleEventError;
        
        // Start loading state
        if (loadingIndicator) loadingIndicator.classList.remove('hidden');
        if (submitButton) submitButton.disabled = true;
    }
    
    function handleEventMessage(event) {
        try {
            const data = JSON.parse(event.data);
            
            // Handle different message types
            if (data.type === 'connection_established') {
                console.log('Stream connection established');
            } else if (data.type === 'stream_complete') {
                console.log('Stream completed');
                closeEventStream();
            } else if (data.type === 'stream_error') {
                handleError(new Error(data.details || 'Stream error'));
                closeEventStream();
            } else if (data.logs) {
                // Process log messages
                data.logs.forEach(log => {
                    processLogMessage(log);
                });
                
                // Check for final report
                if (data.final_report) {
                    handleFinalReport(data.final_report, data.session_id);
                }
            }
        } catch (error) {
            console.error('Error parsing event data:', error);
        }
    }
    
    function handleEventError(error) {
        console.error('EventSource error:', error);
        handleError(new Error('Lost connection to the server'));
        closeEventStream();
    }
    
    function closeEventStream() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        
        // Update UI state
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
        if (submitButton) submitButton.disabled = false;
    }
    
    function processLogMessage(log) {
        switch (log.type) {
            case 'status':
                appendStatusMessage(log.content, log.agent);
                break;
            case 'agent_output':
                appendAgentMessage(log.agent, log.content);
                break;
            case 'plan_step':
                appendPlanStep(log.agent, log.content);
                break;
            case 'separator':
                appendSeparator(log.content);
                break;
            case 'final_report':
                appendFinalReport(log.content);
                break;
            case 'error':
                appendErrorMessage(log.content);
                break;
            default:
                console.log('Unknown log type:', log.type, log);
        }
        
        // Auto-scroll to bottom
        if (resultsContent) {
            resultsContent.scrollTop = resultsContent.scrollHeight;
        }
    }
    
    function handleFinalReport(reportContent, sessionId) {
        // Save the report to the database
        saveReportToDatabase(reportContent, sessionId);
        
        // Update UI to show success
        if (successIndicator) successIndicator.classList.remove('hidden');
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
        
        // Enable the view report button
        if (viewReportButton) viewReportButton.classList.remove('hidden');
    }
    
    async function saveReportToDatabase(reportContent, sessionId) {
        try {
            const response = await fetch('/api/create-report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: reportContent,
                    title: `Analysis for: ${queryInput.value.trim()}`,
                    session_id: sessionId,
                    metadata: {
                        query: queryInput.value.trim()
                    }
                })
            });
            
            if (!response.ok) {
                throw new Error(`Failed to save report: ${response.statusText}`);
            }
            
            const result = await response.json();
            if (result.report_id) {
                currentReportId = result.report_id;
                console.log('Report saved with ID:', currentReportId);
            }
        } catch (error) {
            console.error('Error saving report:', error);
        }
    }
    
    async function loadRecentReports() {
        if (!recentReportsList) return;
        
        try {
            const response = await fetch('/api/recent-reports?limit=5');
            if (!response.ok) {
                throw new Error(`Failed to fetch recent reports: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Clear existing list
            recentReportsList.innerHTML = '';
            
            if (data.reports && data.reports.length > 0) {
                data.reports.forEach(report => {
                    const date = new Date(report.timestamp);
                    const formattedDate = date.toLocaleDateString();
                    
                    const li = document.createElement('li');
                    li.className = 'mb-2';
                    
                    const link = document.createElement('a');
                    link.href = `/report?report_id=${report._id}`;
                    link.className = 'block p-3 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50';
                    
                    const query = report.metadata && report.metadata.query 
                        ? report.metadata.query
                        : 'Unknown query';
                    
                    const truncatedQuery = query.length > 40 
                        ? query.substring(0, 40) + '...' 
                        : query;
                    
                    link.innerHTML = `
                        <div class="font-medium">${truncatedQuery}</div>
                        <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">${formattedDate}</div>
                    `;
                    
                    li.appendChild(link);
                    recentReportsList.appendChild(li);
                });
            } else {
                recentReportsList.innerHTML = '<div class="text-center text-gray-500 dark:text-gray-400 p-4">No recent reports</div>';
            }
        } catch (error) {
            console.error('Error loading recent reports:', error);
            recentReportsList.innerHTML = '<div class="text-center text-red-500 p-4">Failed to load recent reports</div>';
        }
    }
    
    function resetUI() {
        if (resultsContent) resultsContent.innerHTML = '';
        if (successIndicator) successIndicator.classList.add('hidden');
        if (errorIndicator) errorIndicator.classList.add('hidden');
        if (viewReportButton) viewReportButton.classList.add('hidden');
        
        // Reset global variables
        currentReportId = null;
    }
    
    function handleError(error) {
        console.error('Error:', error);
        
        // Update UI to show error
        if (errorIndicator) errorIndicator.classList.remove('hidden');
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
        
        // Add error message to results
        appendErrorMessage(error.message || 'An unknown error occurred');
        
        // Enable the submit button
        if (submitButton) submitButton.disabled = false;
    }
    
    // UI Rendering Functions
    function appendSystemMessage(message) {
        if (!resultsContent) return;
        
        const element = document.createElement('div');
        element.className = 'p-4 mb-4 bg-gray-100 dark:bg-gray-800 rounded-md animate-fade-in';
        element.textContent = message;
        resultsContent.appendChild(element);
    }
    
    function appendStatusMessage(message, agentName) {
        if (!resultsContent) return;
        
        // Check if an active status message for this agent already exists
        const existingStatus = document.querySelector(`.status-message[data-agent="${agentName}"]`);
        if (existingStatus) {
            // Update existing status message
            existingStatus.querySelector('.status-text').textContent = message;
            return;
        }
        
        const element = document.createElement('div');
        element.className = 'status-message p-4 mb-4 bg-gray-50 dark:bg-gray-800/50 rounded-md flex items-center animate-fade-in';
        element.setAttribute('data-agent', agentName || 'system');
        
        element.innerHTML = `
            <div class="mr-3 text-primary-500 dark:text-primary-400">
                <div class="inline-flex">
                    <span class="typing-dot animate-typing-dot mx-0.5 h-2 w-2 bg-primary-500 dark:bg-primary-400 rounded-full"></span>
                    <span class="typing-dot animate-typing-dot mx-0.5 h-2 w-2 bg-primary-500 dark:bg-primary-400 rounded-full"></span>
                    <span class="typing-dot animate-typing-dot mx-0.5 h-2 w-2 bg-primary-500 dark:bg-primary-400 rounded-full"></span>
                </div>
            </div>
            <div class="status-text">${message}</div>
        `;
        
        resultsContent.appendChild(element);
    }
    
    function appendAgentMessage(agentName, content) {
        if (!resultsContent) return;
        
        // Remove any status messages for this agent
        const statusMessage = document.querySelector(`.status-message[data-agent="${agentName}"]`);
        if (statusMessage) {
            statusMessage.remove();
        }
        
        const element = document.createElement('div');
        element.className = `agent-message border-agent-${agentName} animate-fade-in`;
        
        element.innerHTML = `
            <div class="agent-header">
                <div class="agent-icon agent-icon-${agentName}">
                    ${agentName.charAt(0).toUpperCase()}
                </div>
                <div class="agent-name">
                    ${agentName.charAt(0).toUpperCase() + agentName.slice(1)}
                </div>
            </div>
            <div class="agent-content">
                ${formatMessageContent(content)}
            </div>
        `;
        
        resultsContent.appendChild(element);
    }
    
    function appendPlanStep(agentName, content) {
        if (!resultsContent) return;
        
        const element = document.createElement('div');
        element.className = 'plan-step p-3 my-2 bg-gray-50 dark:bg-gray-800/50 rounded-md border border-gray-200 dark:border-gray-700 animate-fade-in';
        
        let contentHtml = '';
        
        // Format step content
        if (typeof content === 'object') {
            for (const [key, value] of Object.entries(content)) {
                contentHtml += `<div class="mb-1"><span class="font-medium">${key}:</span> ${value}</div>`;
            }
        } else {
            contentHtml = `<div>${content}</div>`;
        }
        
        element.innerHTML = contentHtml;
        resultsContent.appendChild(element);
    }
    
    function appendSeparator(content) {
        if (!resultsContent) return;
        
        const element = document.createElement('hr');
        
        // Determine separator style based on content
        if (content && content.length > 100) {
            element.className = 'my-6 border-t-2 border-gray-300 dark:border-gray-600';
        } else if (content && content.length > 50) {
            element.className = 'my-5 border-t border-gray-200 dark:border-gray-700';
        } else {
            element.className = 'my-4 border-t border-gray-100 dark:border-gray-800';
        }
        
        resultsContent.appendChild(element);
    }
    
    function appendFinalReport(content) {
        if (!resultsContent) return;
        
        const element = document.createElement('div');
        element.className = 'final-report p-6 mb-6 bg-white dark:bg-gray-800 rounded-lg border border-primary-200 dark:border-primary-800 shadow-md animate-fade-in';
        
        element.innerHTML = `
            <h3 class="text-lg font-semibold mb-4 text-primary-700 dark:text-primary-300">Final Investment Report</h3>
            <div class="markdown-content">
                ${marked.parse(content)}
            </div>
        `;
        
        resultsContent.appendChild(element);
    }
    
    function appendErrorMessage(content) {
        if (!resultsContent) return;
        
        const element = document.createElement('div');
        element.className = 'error-message p-4 mb-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-md border-l-4 border-red-500 animate-fade-in';
        
        element.innerHTML = `
            <div class="font-medium mb-1">Error</div>
            <div>${content}</div>
        `;
        
        resultsContent.appendChild(element);
    }
    
    function formatMessageContent(content) {
        if (!content) return '<em>No content provided</em>';
        
        // If content is already a string, just return it
        if (typeof content === 'string') {
            return marked.parse(content);
        }
        
        // For objects, stringify them with formatting
        return `<pre class="bg-gray-50 dark:bg-gray-800 p-3 rounded overflow-auto">${JSON.stringify(content, null, 2)}</pre>`;
    }
}); 