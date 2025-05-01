// JavaScript for the session_history.html page

document.addEventListener('DOMContentLoaded', async () => {
    const sessionId = window.location.pathname.split('/').pop();
    
    // Load both messages and reports in parallel
    await Promise.all([
        loadMessages(),
        loadReports()
    ]);
    
    async function loadMessages() {
        try {
            const messagesContainer = document.getElementById('messages-container');
            const loadingMessages = document.getElementById('loading-messages');
            
            if (!messagesContainer) return;
            
            // Show loading indicator
            if (loadingMessages) loadingMessages.style.display = 'block';
            
            const response = await fetch(`/api/history/messages/${sessionId}`);
            const data = await response.json();
            
            // Hide loading indicator
            if (loadingMessages) loadingMessages.style.display = 'none';
            
            // Clear any existing content
            messagesContainer.innerHTML = '';
            
            if (data.messages && data.messages.length > 0) {
                // Sort messages by timestamp
                data.messages
                    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
                    .forEach(message => {
                        const messageElement = document.createElement('div');
                        messageElement.className = `message message-${message.role.toLowerCase()}`;
                        
                        const date = new Date(message.timestamp);
                        const formattedTime = date.toLocaleString();
                        
                        messageElement.innerHTML = `
                            <div class="message-header">
                                ${message.role === 'user' ? 'You' : message.role.charAt(0).toUpperCase() + message.role.slice(1)}
                                <span class="message-time">${formattedTime}</span>
                            </div>
                            <div class="message-content">${message.content}</div>
                        `;
                        
                        messagesContainer.appendChild(messageElement);
                    });
            } else {
                messagesContainer.innerHTML = '<div class="alert alert-info">No messages found for this session.</div>';
            }
        } catch (error) {
            console.error('Error loading messages:', error);
            const messagesContainer = document.getElementById('messages-container');
            if (messagesContainer) {
                messagesContainer.innerHTML = `<div class="alert alert-danger">Error loading messages: ${error.message}</div>`;
            }
            
            const loadingMessages = document.getElementById('loading-messages');
            if (loadingMessages) loadingMessages.style.display = 'none';
        }
    }
    
    async function loadReports() {
        try {
            const reportsContainer = document.getElementById('reports-container');
            const loadingReports = document.getElementById('loading-reports');
            const sessionTitle = document.getElementById('session-title');
            
            if (!reportsContainer) return;
            
            // Show loading indicator
            if (loadingReports) loadingReports.style.display = 'block';
            
            const response = await fetch(`/api/history/reports/${sessionId}`);
            const data = await response.json();
            
            // Hide loading indicator
            if (loadingReports) loadingReports.style.display = 'none';
            
            // Clear any existing content
            reportsContainer.innerHTML = '';
            
            if (data.reports && data.reports.length > 0) {
                // Update page title with first report title
                if (sessionTitle && data.reports[0].title) {
                    sessionTitle.textContent = data.reports[0].title;
                    document.title = `LangAlpha - ${data.reports[0].title}`;
                }
                
                // Display all reports
                data.reports.forEach(report => {
                    const reportElement = document.createElement('div');
                    reportElement.className = 'report-container';
                    
                    const date = new Date(report.timestamp);
                    const formattedTime = date.toLocaleString();
                    
                    reportElement.innerHTML = `
                        <h3>${report.title}</h3>
                        <div class="text-muted mb-3">Generated: ${formattedTime}</div>
                        <div class="report-content">${report.content}</div>
                        <div class="mt-3">
                            <a href="/report?report_id=${report._id}" class="btn btn-primary btn-sm">View Full Report</a>
                        </div>
                    `;
                    
                    reportsContainer.appendChild(reportElement);
                });
            } else {
                reportsContainer.innerHTML = '<div class="alert alert-info">No reports found for this session.</div>';
            }
        } catch (error) {
            console.error('Error loading reports:', error);
            const reportsContainer = document.getElementById('reports-container');
            if (reportsContainer) {
                reportsContainer.innerHTML = `<div class="alert alert-danger">Error loading reports: ${error.message}</div>`;
            }
            
            const loadingReports = document.getElementById('loading-reports');
            if (loadingReports) loadingReports.style.display = 'none';
        }
    }
}); 