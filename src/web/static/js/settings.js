// JavaScript for the settings.html page

document.addEventListener('DOMContentLoaded', function() {
    console.log("Settings page loaded");

    // Ensure that window.currentWorkflowConfig exists
    try {
        if (typeof window.currentWorkflowConfig === 'undefined') {
            window.currentWorkflowConfig = loadWorkflowConfig();
            console.log("Initialized window.currentWorkflowConfig:", window.currentWorkflowConfig);
        }
    } catch (e) {
        console.error("Error initializing currentWorkflowConfig:", e);
    }

    // Load current config and populate form
    loadAndPopulateConfigForm();

    // Set up button event listeners
    setupButtonHandlers();

    // Load recent reports
    loadRecentReports();
});

// --- Configuration Logic ---

// Default config values (matching .env.example)
const DEFAULT_LLM_CONFIGS = {
    reasoning: { model: 'gpt-4o', provider: 'OPENAI' },
    basic:     { model: 'gpt-4o-mini', provider: 'OPENAI' },
    coding:    { model: 'gpt-4o', provider: 'OPENAI' },
    economic:  { model: 'gpt-4o-mini', provider: 'OPENAI' }
};

const DEFAULT_WORKFLOW_CONFIG = {
    budget: 'low', // Match the default set in web/main.py WorkflowConfig
    llm_configs: DEFAULT_LLM_CONFIGS
};

// Initialize currentWorkflowConfig at global scope
let currentWorkflowConfig = null;

// Set up button handlers
function setupButtonHandlers() {
    const saveBtn = document.getElementById('save-config-btn');
    const resetBtn = document.getElementById('reset-config-btn');
    
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            saveConfigFromForm();
            showToast('Settings saved successfully!');
        });
    } else {
        console.error("#save-config-btn not found");
    }
    
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to reset all settings to default values?')) {
                resetToDefaults();
                showToast('Settings reset to defaults');
            }
        });
    } else {
        console.error("#reset-config-btn not found");
    }
}

// Load current config and populate the form
function loadAndPopulateConfigForm() {
    // Load configuration 
    currentWorkflowConfig = loadWorkflowConfig();
    
    // Populate the form fields
    populateConfigForm(currentWorkflowConfig);
    
    console.log("Form populated with current config:", currentWorkflowConfig);
}

// Populate the form with current/default settings
function populateConfigForm(config) {
    const budgetSelect = document.getElementById('config-budget');
    if (budgetSelect) {
        budgetSelect.value = config.budget || DEFAULT_WORKFLOW_CONFIG.budget;
    }

    const llmConfigs = config.llm_configs || DEFAULT_LLM_CONFIGS;
    
    Object.keys(llmConfigs).forEach(type => {
        const modelInput = document.getElementById(`config-${type}-model`);
        const providerSelect = document.getElementById(`config-${type}-provider`);
        if (modelInput && providerSelect) {
            modelInput.value = llmConfigs[type].model;
            providerSelect.value = llmConfigs[type].provider.toUpperCase();
        }
    });
}

// Read settings from form and save to localStorage
function saveConfigFromForm() {
    const budget = document.getElementById('config-budget').value;
    const llmConfigs = {
        reasoning: { model: "", provider: "" },
        basic: { model: "", provider: "" },
        coding: { model: "", provider: "" },
        economic: { model: "", provider: "" }
    };
    
    ['reasoning', 'basic', 'coding', 'economic'].forEach(type => {
        const modelInput = document.getElementById(`config-${type}-model`);
        const providerSelect = document.getElementById(`config-${type}-provider`);
        
        // Ensure both elements exist before attempting to use them
        if (!modelInput || !providerSelect) {
            console.error(`Missing form elements for LLM type: ${type}`);
            return;
        }
        
        const model = modelInput.value.trim();
        const provider = providerSelect.value.trim();
        
        // Validate values are not empty, use defaults if they are
        llmConfigs[type] = {
            model: model || DEFAULT_LLM_CONFIGS[type].model,
            provider: (provider || DEFAULT_LLM_CONFIGS[type].provider).toUpperCase()
        };
    });

    const config = {
        budget: budget,
        llm_configs: llmConfigs
    };
    
    // Log the exact structure being saved
    console.log("About to save workflow config:", JSON.stringify(config));
    
    // Save to localStorage
    localStorage.setItem('workflowConfig', JSON.stringify(config));
    
    // Update the current workflow config
    currentWorkflowConfig = config;
    
    return config;
}

// Reset all form fields to default values
function resetToDefaults() {
    localStorage.removeItem('workflowConfig');
    populateConfigForm(DEFAULT_WORKFLOW_CONFIG);
    console.log("Reset to default workflow config");
}

// Load config from localStorage or use defaults
function loadWorkflowConfig() {
    const savedConfig = localStorage.getItem('workflowConfig');
    if (savedConfig) {
        try {
            const parsed = JSON.parse(savedConfig);
            // More thorough validation to ensure the object has the required properties
            if (parsed && 
                parsed.budget && 
                parsed.llm_configs &&
                parsed.llm_configs.reasoning && 
                parsed.llm_configs.reasoning.model && 
                parsed.llm_configs.reasoning.provider &&
                parsed.llm_configs.basic && 
                parsed.llm_configs.basic.model && 
                parsed.llm_configs.basic.provider &&
                parsed.llm_configs.coding && 
                parsed.llm_configs.coding.model && 
                parsed.llm_configs.coding.provider &&
                parsed.llm_configs.economic && 
                parsed.llm_configs.economic.model && 
                parsed.llm_configs.economic.provider) {
                
                console.log("Loaded valid workflow config from localStorage:", parsed);
                return parsed;
            } else {
                console.warn("Saved config found but missing required properties. Using defaults.");
            }
        } catch (e) {
            console.error("Error parsing saved workflow config:", e);
        }
    }
    console.log("Using default workflow config");
    return JSON.parse(JSON.stringify(DEFAULT_WORKFLOW_CONFIG)); // Deep copy default
}

// --- Utilities ---

// Toast notification function
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-16 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white px-6 py-3 rounded-lg shadow-lg animate-fade-in z-50';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('opacity-0', 'transition-opacity', 'duration-500');
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

// Back to top button functionality
const backToTopButton = document.getElementById('backToTop');

// Show button when scrolling down
window.addEventListener('scroll', () => {
    if (window.scrollY > 300) {
        backToTopButton.classList.remove('opacity-0', 'translate-y-5');
    } else {
        backToTopButton.classList.add('opacity-0', 'translate-y-5');
    }
});

// Scroll to top when clicked
backToTopButton.addEventListener('click', () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

// Function to load recent reports from MongoDB
function loadRecentReports() {
    const recentReportsList = document.getElementById('recent-reports-list');

    if (!recentReportsList) {
        console.error('Recent reports list element not found');
        return;
    }

    // Clear any existing reports
    recentReportsList.innerHTML = `
        <li class="mb-1 animate-pulse">
            <div class="flex items-center p-3 rounded-md text-gray-700 dark:text-gray-300">
                <span class="mr-3">🕒</span>
                Loading recent reports...
            </div>
        </li>
    `;

    // Fetch recent reports from API
    fetch('/api/recent-reports?limit=5')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to fetch recent reports: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data || !data.reports || !Array.isArray(data.reports)) {
                throw new Error('Invalid data structure returned from API');
            }

            if (data.reports.length === 0) {
                recentReportsList.innerHTML = `
                    <li class="mb-1">
                        <div class="flex items-center p-3 rounded-md text-gray-700 dark:text-gray-300">
                            <span class="mr-3">📝</span>
                            No recent reports found
                        </div>
                    </li>
                `;
                return;
            }

            // Clear the list
            recentReportsList.innerHTML = '';

            // Add each report to the list
            data.reports.forEach(report => {
                const reportDate = new Date(report.timestamp).toLocaleString();
                
                // Prioritize the report title over the query text
                const displayTitle = report.title || 
                    (report.metadata && report.metadata.query ? report.metadata.query : 'Investment Analysis');

                const shortTitle = displayTitle.length > 30
                    ? displayTitle.substring(0, 30) + '...'
                    : displayTitle;

                const reportItem = document.createElement('li');
                reportItem.className = 'mb-1';
                reportItem.innerHTML = `
                    <a href="/report?report_id=${report._id}" class="flex items-center p-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 transition-colors">
                        <span class="mr-3">📄</span>
                        <div class="flex flex-col">
                            <span class="text-sm">${shortTitle}</span>
                            <span class="text-xs text-gray-500">${reportDate}</span>
                        </div>
                    </a>
                `;
                recentReportsList.appendChild(reportItem);
            });
        })
        .catch(error => {
            console.error('Error loading recent reports:', error);
            recentReportsList.innerHTML = `
                <li class="mb-1">
                    <div class="flex items-center p-3 rounded-md text-red-700 dark:text-red-400">
                        <span class="mr-3">❌</span>
                        Error loading reports: ${error.message}
                    </div>
                </li>
            `;
        });
} 