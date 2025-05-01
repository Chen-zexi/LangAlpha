// JavaScript for the history.html page

document.addEventListener('DOMContentLoaded', async () => {
    const sessionsContainer = document.getElementById('sessions-container');
    const loadingSessions = document.getElementById('loading-sessions');
    const noSessions = document.getElementById('no-sessions');
    const backButton = document.getElementById('back-button');
    
    // Back button event listener
    if (backButton) {
        backButton.addEventListener('click', () => {
            window.location.href = '/';
        });
    }
    
    // Load sessions
    try {
        const response = await fetch('/api/history/sessions');
        const data = await response.json();
        
        // Hide loading indicator
        if (loadingSessions) loadingSessions.classList.add('d-none');
        
        if (data.sessions && data.sessions.length > 0) {
            // Sort sessions by timestamp (newest first)
            data.sessions.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            
            data.sessions.forEach(session => {
                const sessionCard = document.createElement('div');
                sessionCard.className = 'col-md-6 col-lg-4';
                
                const date = new Date(session.timestamp);
                const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                
                sessionCard.innerHTML = `
                    <div class="card h-100">
                        <div class="card-body">
                            <h5 class="card-title">Session ${session._id.substring(0, 8)}...</h5>
                            <p class="card-text">
                                <small class="text-muted">Created: ${formattedDate}</small>
                            </p>
                            <p class="card-text">
                                Messages: ${session.message_count || 0}
                                <br>
                                Reports: ${session.report_count || 0}
                            </p>
                        </div>
                        <div class="card-footer bg-transparent border-top-0">
                            <a href="/history/${session._id}" class="btn btn-primary">View Details</a>
                        </div>
                    </div>
                `;
                
                if (sessionsContainer) sessionsContainer.appendChild(sessionCard);
            });
        } else {
            if (noSessions) noSessions.classList.remove('d-none');
        }
    } catch (error) {
        console.error('Error loading sessions:', error);
        if (loadingSessions) loadingSessions.classList.add('d-none');
        
        const errorAlert = document.createElement('div');
        errorAlert.className = 'alert alert-danger mt-4';
        errorAlert.textContent = `Error loading sessions: ${error.message}`;
        if (sessionsContainer) sessionsContainer.appendChild(errorAlert);
    }
}); 