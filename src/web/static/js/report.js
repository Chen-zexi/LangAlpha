// JavaScript for the report.html page

document.addEventListener('DOMContentLoaded', () => {
    // Get report ID from URL query parameters
    const urlParams = new URLSearchParams(window.location.search);
    const reportId = urlParams.get('report_id');
    
    // DOM Elements
    const reportTitle = document.getElementById('report-title');
    const reportQuery = document.getElementById('report-query');
    const reportTimestamp = document.getElementById('report-timestamp');
    const reportContent = document.getElementById('report-content');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessage = document.getElementById('error-message');
    const backButton = document.getElementById('back-button');
    const printButton = document.getElementById('print-button');
    const downloadButton = document.getElementById('download-button');
    
    // Load report data if a report ID is provided
    if (reportId) {
        loadReport(reportId);
    } else {
        showError('No report ID provided. Please return to the main page and try again.');
    }
    
    // Event listeners
    if (backButton) {
        backButton.addEventListener('click', () => {
            // Return to the main page
            window.location.href = '/';
        });
    }
    
    if (printButton) {
        printButton.addEventListener('click', () => {
            window.print();
        });
    }
    
    if (downloadButton) {
        downloadButton.addEventListener('click', () => {
            // Trigger print for now (could be replaced with actual PDF download)
            window.print();
        });
    }
    
    // Functions
    async function loadReport(id) {
        try {
            showLoading(true);
            
            const response = await fetch(`/api/history/report/${id}`);
            
            if (!response.ok) {
                throw new Error(`Failed to load report: ${response.statusText}`);
            }
            
            const report = await response.json();
            
            // Update the UI with report data
            displayReport(report);
            
        } catch (error) {
            console.error('Error loading report:', error);
            showError(error.message || 'Failed to load report');
        } finally {
            showLoading(false);
        }
    }
    
    function displayReport(report) {
        // Set title
        document.title = `LangAlpha | ${report.title || 'Investment Report'}`;
        
        // Display report metadata
        if (reportTitle) {
            reportTitle.textContent = report.title || 'Investment Report';
        }
        
        if (reportQuery && report.metadata && report.metadata.query) {
            reportQuery.textContent = report.metadata.query;
        } else if (reportQuery) {
            reportQuery.parentElement.classList.add('hidden');
        }
        
        if (reportTimestamp && report.timestamp) {
            const date = new Date(report.timestamp);
            reportTimestamp.textContent = date.toLocaleString();
        }
        
        // Display report content with markdown parsing
        if (reportContent && report.content) {
            // Parse markdown and sanitize HTML
            const parsedContent = DOMPurify.sanitize(marked.parse(report.content));
            reportContent.innerHTML = parsedContent;
            
            // Add markdown content class for styling
            reportContent.classList.add('markdown-content');
        }
    }
    
    function showLoading(isLoading) {
        if (!loadingIndicator) return;
        
        if (isLoading) {
            loadingIndicator.classList.remove('hidden');
            if (reportContent) reportContent.classList.add('hidden');
            if (errorMessage) errorMessage.classList.add('hidden');
        } else {
            loadingIndicator.classList.add('hidden');
            if (reportContent) reportContent.classList.remove('hidden');
        }
    }
    
    function showError(message) {
        if (!errorMessage) return;
        
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
        
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
        if (reportContent) reportContent.classList.add('hidden');
    }
}); 