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
            // Use html2pdf.js to generate a PDF containing only the report content
            const reportContent = document.getElementById('report-content');
            
            if (!reportContent || reportContent.innerHTML.trim() === '') {
                console.error('No report content found');
                alert('No report content available to download');
                return;
            }
            
            const originalButtonText = downloadButton.innerHTML;
            
            // Show a loading spinner in the button
            downloadButton.innerHTML = `
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Preparing PDF...
            `;
            downloadButton.disabled = true;
            
            // Get the report title for the filename
            const reportTitle = document.getElementById('report-title').textContent || 'Investment Report';
            const fileName = reportTitle.replace(/[^a-z0-9]/gi, '_').toLowerCase() + '.pdf';
            
            // Configure PDF options with proper fonts and styles 
            const options = {
                margin: 15,
                filename: fileName,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { 
                    scale: 2, 
                    useCORS: true, 
                    logging: false,
                    letterRendering: true
                },
                jsPDF: { 
                    unit: 'mm', 
                    format: 'a4', 
                    orientation: 'portrait',
                    compress: true
                }
            };
            
            // Generate PDF directly from the actual content element
            // This avoids issues with hidden containers
            html2pdf()
                .from(reportContent)
                .set(options)
                .save()
                .then(() => {
                    // Restore original button text
                    downloadButton.innerHTML = originalButtonText;
                    downloadButton.disabled = false;
                })
                .catch(error => {
                    console.error('Error generating PDF:', error);
                    // Show error in button
                    downloadButton.innerHTML = 'Error creating PDF';
                    setTimeout(() => {
                        downloadButton.innerHTML = originalButtonText;
                        downloadButton.disabled = false;
                    }, 3000);
                });
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
            reportQuery.parentElement.style.display = 'none';
        }
        
        if (reportTimestamp && report.timestamp) {
            const date = new Date(report.timestamp);
            reportTimestamp.textContent = date.toLocaleString();
        } else if (reportTimestamp) {
            reportTimestamp.parentElement.style.display = 'none';
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
            loadingIndicator.style.display = 'block';
            if (reportContent) reportContent.style.display = 'none';
            if (errorMessage) errorMessage.style.display = 'none';
        } else {
            loadingIndicator.style.display = 'none';
            if (reportContent) reportContent.style.display = 'block';
        }
    }
    
    function showError(message) {
        if (!errorMessage) return;
        
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
        
        if (loadingIndicator) loadingIndicator.style.display = 'none';
        if (reportContent) reportContent.style.display = 'none';
    }
}); 