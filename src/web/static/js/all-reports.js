// JavaScript for the all-reports.html page

document.addEventListener('DOMContentLoaded', function() {
    console.log("All reports page loaded.");
    
    // Elements
    const loadingIndicator = document.getElementById('loading-indicator');
    const emptyState = document.getElementById('empty-state');
    const errorState = document.getElementById('error-state');
    const errorMessage = document.getElementById('error-message');
    const reportsContainer = document.getElementById('reports-container');
    const pagination = document.getElementById('pagination');
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const currentPageEl = document.getElementById('current-page');
    const totalPagesEl = document.getElementById('total-pages');
    const sortBySelect = document.getElementById('sort-by');
    const searchInput = document.getElementById('search-reports');
    const backButton = document.getElementById('back-button');
    
    // State
    let allReports = [];
    let filteredReports = [];
    let currentPage = 1;
    let reportsPerPage = 9; // 3x3 grid
    let currentSort = loadSortPreference() || 'date-desc';
    let currentSearch = '';
    
    // Load saved sort preference from localStorage
    function loadSortPreference() {
        const savedSort = localStorage.getItem('reportsSort');
        if (savedSort) {
            console.log("Loaded saved sort preference:", savedSort);
            return savedSort;
        }
        return null;
    }
    
    // Save sort preference to localStorage
    function saveSortPreference(sortValue) {
        localStorage.setItem('reportsSort', sortValue);
        console.log("Saved sort preference:", sortValue);
        
        // Show brief visual feedback (optional)
        showToast('Sort preference saved');
    }
    
    // Apply saved preference to the select element
    if (sortBySelect && currentSort) {
        sortBySelect.value = currentSort;
    }
    
    // Setup event listeners
    backButton.addEventListener('click', function() {
        window.location.href = '/';
    });
    
    sortBySelect.addEventListener('change', function() {
        currentSort = this.value;
        currentPage = 1; // Reset to first page when sorting changes
        saveSortPreference(currentSort);
        filterAndDisplayReports();
    });
    
    searchInput.addEventListener('input', debounce(function() {
        currentSearch = this.value.trim().toLowerCase();
        currentPage = 1; // Reset to first page when search changes
        filterAndDisplayReports();
    }, 300));
    
    prevPageBtn.addEventListener('click', function() {
        if (currentPage > 1) {
            currentPage--;
            displayReportsForCurrentPage();
        }
    });
    
    nextPageBtn.addEventListener('click', function() {
        const totalPages = Math.ceil(filteredReports.length / reportsPerPage);
        if (currentPage < totalPages) {
            currentPage++;
            displayReportsForCurrentPage();
        }
    });
    
    // Load reports on page load
    fetchAllReports();
    
    // Function to fetch all reports from API
    function fetchAllReports() {
        // Show loading indicator
        loadingIndicator.classList.remove('hidden');
        emptyState.classList.add('hidden');
        errorState.classList.add('hidden');
        reportsContainer.classList.add('hidden');
        pagination.classList.add('hidden');
        
        // Fetch reports with a high limit to get all
        fetch('/api/recent-reports?limit=1000')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Failed to fetch reports: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Hide loading indicator
                loadingIndicator.classList.add('hidden');
                
                if (!data || !data.reports || !Array.isArray(data.reports)) {
                    throw new Error('Invalid data structure returned from API');
                }
                
                if (data.reports.length === 0) {
                    // Show empty state
                    emptyState.classList.remove('hidden');
                    return;
                }
                
                // Store reports and display them
                allReports = data.reports;
                filterAndDisplayReports();
            })
            .catch(error => {
                console.error('Error loading reports:', error);
                loadingIndicator.classList.add('hidden');
                errorState.classList.remove('hidden');
                errorMessage.textContent = error.message || 'An unexpected error occurred. Please try again later.';
            });
    }
    
    // Function to filter and sort reports based on user criteria
    function filterAndDisplayReports() {
        // Filter reports based on search text
        if (currentSearch) {
            filteredReports = allReports.filter(report => {
                const title = (report.title || '').toLowerCase();
                const query = ((report.metadata && report.metadata.query) || '').toLowerCase();
                return title.includes(currentSearch) || query.includes(currentSearch);
            });
        } else {
            filteredReports = [...allReports];
        }
        
        // Sort reports based on selected option
        filteredReports.sort((a, b) => {
            switch (currentSort) {
                case 'date-desc':
                    return new Date(b.timestamp) - new Date(a.timestamp);
                case 'date-asc':
                    return new Date(a.timestamp) - new Date(b.timestamp);
                case 'title-asc':
                    return (a.title || '').localeCompare(b.title || '');
                case 'title-desc':
                    return (b.title || '').localeCompare(a.title || '');
                default:
                    return new Date(b.timestamp) - new Date(a.timestamp);
            }
        });
        
        // Check if we have any reports after filtering
        if (filteredReports.length === 0) {
            reportsContainer.classList.add('hidden');
            pagination.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }
        
        // Display reports and setup pagination
        reportsContainer.classList.remove('hidden');
        emptyState.classList.add('hidden');
        
        displayReportsForCurrentPage();
    }
    
    // Function to display reports for the current page
    function displayReportsForCurrentPage() {
        // Clear previous reports
        reportsContainer.innerHTML = '';
        
        // Calculate pagination
        const totalReports = filteredReports.length;
        const totalPages = Math.ceil(totalReports / reportsPerPage);
        const startIndex = (currentPage - 1) * reportsPerPage;
        const endIndex = Math.min(startIndex + reportsPerPage, totalReports);
        
        // Update pagination UI
        if (totalPages > 1) {
            pagination.classList.remove('hidden');
            currentPageEl.textContent = currentPage;
            totalPagesEl.textContent = totalPages;
            prevPageBtn.disabled = currentPage === 1;
            nextPageBtn.disabled = currentPage === totalPages;
        } else {
            pagination.classList.add('hidden');
        }
        
        // Get reports for current page
        const currentPageReports = filteredReports.slice(startIndex, endIndex);
        
        // Create report cards
        currentPageReports.forEach(report => {
            const card = createReportCard(report);
            reportsContainer.appendChild(card);
        });
    }
    
    // Function to create a report card element
    function createReportCard(report) {
        const card = document.createElement('div');
        // Improved card design with consistent spacing and better alignment
        card.className = 'bg-white dark:bg-gray-800 rounded-xl shadow-md hover:shadow-lg transition-shadow duration-300 border border-gray-200 dark:border-gray-700 mb-4';
        
        // Format date more nicely and make it muted
        const reportDate = new Date(report.timestamp);
        const formattedDate = reportDate.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
        const formattedTime = reportDate.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        const friendlyTimestamp = `${formattedDate} · ${formattedTime}`; // e.g., "May 3, 2025 · 05:53"
        
        // Get report title or fallback
        const reportTitle = report.title || 
            (report.metadata && report.metadata.query ? report.metadata.query : 'Investment Analysis');
        
        card.innerHTML = `
            <div class="p-6">
                <div class="flex items-start justify-between">
                    <div class="flex-grow mr-4">
                        <div class="flex items-center mb-2">
                            <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 line-clamp-2" title="${reportTitle}">${reportTitle}</h3>
                            <span class="ml-3 bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300 text-xs font-medium px-2.5 py-0.5 rounded-full">Report</span>
                        </div>
                        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Generated: ${friendlyTimestamp}</p>
                    </div>
                </div>
                <div class="flex justify-end mt-2">
                    <a href="/report?session_id=${report.session_id}" 
                       class="inline-flex items-center px-4 py-2 text-sm font-medium bg-primary-600 hover:bg-primary-700 text-white rounded-md transition-colors shadow-sm">
                        View Report
                        <i class="fa-solid fa-arrow-right ml-2"></i>
                    </a>
                </div>
            </div>
        `;
        
        return card;
    }
    
    // Utility function for debouncing
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }
    
    // Toast notification function (similar to settings.js)
    function showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'fixed bottom-16 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white px-6 py-3 rounded-lg shadow-lg animate-fade-in z-50';
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('opacity-0', 'transition-opacity', 'duration-500');
            setTimeout(() => toast.remove(), 500);
        }, 2000);
    }
}); 