// JavaScript for the index.html page

// Initialize core variables
let eventSource = null;
let currentAgentProcessing = null;
let statusMessages = [];
let allLogElements = [];
let currentSessionId = null; // NEW: Track the session ID for the current run
let supervisorStatusMessages = []; // NEW: Track supervisor status messages

// Default config values (matching .env.example)
const DEFAULT_LLM_CONFIGS = {
    reasoning: { model: 'gemini-2.5-pro-preview-05-06', provider: 'GEMINI' },
    basic:     { model: 'gpt-4.1', provider: 'OPENAI' },
    coding:    { model: 'gemini-2.5-pro-preview-05-06', provider: 'GEMINI' },
    economic:  { model: 'gpt-4.1-mini', provider: 'OPENAI' },
};

const DEFAULT_WORKFLOW_CONFIG = {
    budget: 'low', // Match the default set in web/main.py WorkflowConfig
    llm_configs: DEFAULT_LLM_CONFIGS
};

// Initialize config state
let currentWorkflowConfig = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed.");

    // Load workflow configuration
    currentWorkflowConfig = loadWorkflowConfig();
    console.log("Loaded workflow config on page load:", currentWorkflowConfig);

    // Configure marked for security and code highlighting
    marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: true,
        highlight: function(code, lang) {
            if (hljs && lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (e) {
                    console.error('Highlight.js error:', e);
                }
            }
            return code;
        }
    });

    // Set up example chips
    setupExampleQueries();

    // Check if we're returning from report page and restore state if needed
    // This should run on DOMContentLoaded to restore main content before first paint
    checkReturnFromReport();
    
    
    // Set up the View All Reports button directly here
    console.log("Setting up View All Reports button directly");
    const viewAllReportsBtn = document.getElementById('view-all-reports-btn');
    console.log("View All Reports Button:", viewAllReportsBtn);
    
    if (viewAllReportsBtn) {
        viewAllReportsBtn.addEventListener('click', function() {
            console.log("View All Reports button clicked");
            window.location.href = '/all-reports';
        });
    } else {
        console.error("View All Reports button not found in DOM");
    }

    // NOTE: loadRecentReports() is now called in the 'pageshow' event handler
    // to ensure it runs on initial load AND bfcache restores.
});

// Use pageshow to ensure recent reports load on initial load and bfcache restore
window.addEventListener('pageshow', function(event) {
    console.log(`Page shown: ${event.persisted ? 'from bfcache' : 'initial load'}`);
    // Always load recent reports when the page is shown
    console.log("Loading recent reports from MongoDB (on pageshow)...");
    loadRecentReports();
});

const submitBtn = document.getElementById('submit-btn');
const queryInput = document.getElementById('query');
const outputDiv = document.getElementById('output');
const statusIndicator = document.getElementById('status-indicator');

// Add global variables to track planner output and steps
window.currentPlannerOutput = null;
window.currentPlanStepsContainer = null;
window.plannerTitle = null; // Track the planner title
let reportButtonElement = null; // Store reference to the report button if created

// --- Start: Configuration Functions ---

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

// --- End: Configuration Functions ---

// Function to check if we're returning from the report page
function checkReturnFromReport() {
    const returnFromReport = localStorage.getItem('returnFromReport');
    if (returnFromReport === 'true') {
        // Clear the flag
        localStorage.removeItem('returnFromReport');

        // Get the query and cached content
        const reportQuery = localStorage.getItem('reportQuery');
        const cachedOutputHtml = localStorage.getItem('cachedOutputHtml');
        const scrollPosition = parseInt(localStorage.getItem('scrollPosition') || '0');
        const statusText = localStorage.getItem('statusText');
        const statusClass = localStorage.getItem('statusClass');
        currentSessionId = localStorage.getItem('reportSessionId'); // Restore session ID

        if (reportQuery && cachedOutputHtml) {
            // Set the query input
            queryInput.value = reportQuery;

            // Restore the cached content
            outputDiv.innerHTML = cachedOutputHtml;

            // Restore status
            if (statusText && statusClass) {
                updateStatus(statusText, statusClass);
            } else {
                updateStatus('Report Ready', 'success');
            }

            // Restore scroll position after a brief delay to ensure content is rendered
            setTimeout(() => {
                outputDiv.scrollTop = scrollPosition;
            }, 100);

            // Re-attach event listeners to interactive elements
            reattachEventListeners();

            // Show a toast notification that we've returned
            showToast('Returned to previous results');

            return true;
        }
    }
    return false;
}

// Helper function to reattach event listeners to cached content
function reattachEventListeners() {
    // Reattach event listeners to plan step toggles
    const toggleButtons = outputDiv.querySelectorAll('.plan-steps-heading');
    toggleButtons.forEach(button => {
        const container = button.nextElementSibling;
        if (container && container.classList.contains('plan-steps-container')) {
            button.addEventListener('click', function() {
                const arrow = this.querySelector('.chevron-icon');
                const isHidden = container.style.display === 'none';
                container.style.display = isHidden ? 'block' : 'none';
                arrow.style.transform = isHidden ? 'rotate(90deg)' : 'rotate(0deg)';
                
                // Trigger resize after toggle
                setTimeout(resizeResultsContainer, 10);
            });
        }
    });

    // Reattach view report button functionality using session ID
    reportButtonElement = outputDiv.querySelector('button.view-report-button'); // Find the button
    if (reportButtonElement) {
        reportButtonElement.onclick = savePageStateAndNavigateToReport; // Reattach the specific handler
    }
}

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

// Function to set example query from chips
function setExampleQuery(query) {
    queryInput.value = query;
    queryInput.focus();
    // Optionally auto-submit
    // submitBtn.click();
}

// Function to setup example queries - can be customized
function setupExampleQueries() {
    const exampleChips = document.querySelectorAll('.examples-container .example-chip');
    exampleChips.forEach(chip => {
        chip.addEventListener('click', () => {
            setExampleQuery(chip.textContent);
        });
    });
}

// Function to sanitize text to prevent XSS
function sanitizeHTML(str) {
    return DOMPurify.sanitize(str);
}

// Function to display content without streaming effect
function displayContent(element, markdown) {
    try {
        const parsedContent = marked.parse(markdown);
        const sanitizedContent = sanitizeHTML(parsedContent);

        // Create a container for the content
        const contentContainer = document.createElement('div');
        contentContainer.className = 'markdown-content px-4 py-2 pl-10';
        contentContainer.innerHTML = sanitizedContent;

        element.appendChild(contentContainer);

        // Force recalculation of container size
        resizeResultsContainer();
    } catch (e) {
        console.error("Markdown parsing error:", e);
        element.innerHTML = sanitizeHTML(markdown);
        resizeResultsContainer();
    }
}

// Function to display text
function displayText(element, text) {
    element.innerHTML += sanitizeHTML(text);
    resizeResultsContainer();
}

// Function to animate typing dots using Motion One
function animateTypingDots(containerElement) {
    if (!containerElement) return;
    
    const dots = containerElement.querySelectorAll('.typing-dot');
    if (!dots || dots.length === 0) return;
    
    dots.forEach((dot, index) => {
        // Different delay for each dot
        const delay = index * 0.2;
        
        // Create a repeating animation
        Motion.animate(
            dot,
            { transform: ['translateY(0px)', 'translateY(-3px)', 'translateY(0px)'] },
            { 
                duration: 1.5,
                delay,
                repeat: Infinity,
                easing: "ease-in-out"
            }
        );
    });
}

// Function to format and append log messages
function appendLogMessage(log) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('log-message');

    if (log.type) {
        messageElement.classList.add(`log-type-${log.type}`);
        messageElement.setAttribute('data-log-type', log.type);
    }

    if (log.agent) {
        messageElement.classList.add(`log-agent-${log.agent}`);
        messageElement.setAttribute('data-log-agent', log.agent);
    }

    // Store reference to status logs for potential hiding later
    if (log.type === 'status') {
        statusMessages.push(messageElement);
    }

    switch (log.type) {
        case 'status':
            // Create a status message
            if (log.agent && (log.content.includes('waiting for') || log.content.includes('thinking') ||
                log.content.includes('gathering') || log.content.includes('coding') ||
                log.content.includes('retrieving') || log.content.includes('browsing') ||
                log.content.includes('analyzing') || log.content.includes('preparing'))) {

                // Create an agent processing indicator
                const agentName = log.agent.charAt(0).toUpperCase() + log.agent.slice(1);
                messageElement.classList.add('p-3', 'mb-2', 'bg-white', 'dark:bg-gray-800', 'rounded-md', 'shadow-sm', 'border-l-3', `border-l-agent-${log.agent}`);
                messageElement.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold agent-icon-${log.agent}">${agentName.charAt(0)}</div>
                        <div>
                            <div class="text-sm font-semibold">${agentName}</div>
                            <div class="text-xs text-gray-500 dark:text-gray-400">AI Agent</div>
                        </div>
                    </div>
                    <div class="pl-10 mt-2 text-gray-600 dark:text-gray-400 flex items-center">
                        ${sanitizeHTML(log.content)}
                        <div class="ml-2 flex gap-1 typing-dots-container">
                            <div class="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 typing-dot"></div>
                            <div class="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 typing-dot"></div>
                            <div class="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 typing-dot"></div>
                        </div>
                    </div>
                `;

                // Save reference to current processing agent for potential hiding later
                if (log.agent) {
                    // Check if there's already a processing message for this agent
                    const existingProcessing = allLogElements.find(el => 
                        el.classList.contains('log-agent-' + log.agent) && 
                        el.querySelector('.typing-dot')
                    );
                    
                    if (existingProcessing) {
                        // Use Motion One to animate the removal
                        Motion.animate(existingProcessing, 
                            { opacity: 0, height: 0, overflow: "hidden" }, 
                            { duration: 0.3, easing: "ease-out" }
                        ).then(() => {
                            try {
                                existingProcessing.remove();
                                // Remove from allLogElements array
                                const index = allLogElements.indexOf(existingProcessing);
                                if (index > -1) {
                                    allLogElements.splice(index, 1);
                                }
                            } catch (e) {
                                console.error("Error removing existing processing status:", e);
                            }
                        });
                    }

                    currentAgentProcessing = messageElement;
                }
            } else {
                messageElement.innerHTML = `
                    <p class="px-4 py-2 italic text-gray-500 dark:text-gray-400 text-sm flex items-center">
                        <span class="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 mr-2"></span>
                        ${sanitizeHTML(log.content)}
                    </p>
                `;
            }
            break;

        case 'agent_output':
            // Create an agent output container
            messageElement.className = 'mb-3';

            // Create the agent container with the right styling
            const agentContainer = document.createElement('div');
            agentContainer.className = `p-4 bg-white dark:bg-gray-800 rounded-md shadow-sm border-l-3 border-l-agent-${log.agent}`;

            // Add the agent header
            agentContainer.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold agent-icon-${log.agent}">${log.agent.charAt(0).toUpperCase()}</div>
                    <div>
                        <div class="text-sm font-semibold">${log.agent.charAt(0).toUpperCase() + log.agent.slice(1)}</div>
                        <div class="text-xs text-gray-500 dark:text-gray-400">AI Agent</div>
                    </div>
                </div>
            `;

            // Create container for the content
            const contentContainer = document.createElement('div');
            contentContainer.className = 'mt-3';
            agentContainer.appendChild(contentContainer);

            // Special handling for reporter agent - show the report button IF report is saved
            if (log.agent === 'reporter' && log.content.includes('report has been saved')) {
                // Create a special container with the report button
                const reporterContainer = document.createElement('div');
                reporterContainer.className = 'mt-2 pl-10 flex items-center justify-between';

                // Add the standard text on the left
                const textDiv = document.createElement('div');
                textDiv.className = 'text-gray-700 dark:text-gray-300';
                textDiv.textContent = log.content; 
                reporterContainer.appendChild(textDiv);

                // Add the "View Report" button on the right
                const buttonDiv = document.createElement('div');
                buttonDiv.className = 'ml-4';
                // Use the savePageStateAndNavigateToReport function
                buttonDiv.innerHTML = `
                    <button onclick="savePageStateAndNavigateToReport()" class="view-report-button px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 text-white text-sm font-medium rounded shadow-sm hover:shadow transform hover:-translate-y-0.5 active:translate-y-0 transition-all duration-300">
                        View Complete Investment Report
                    </button>
                `;
                reportButtonElement = buttonDiv.querySelector('button');
                reporterContainer.appendChild(buttonDiv);

                // Replace the standard content container with our custom one
                contentContainer.appendChild(reporterContainer);

                // Update status to success when reporter finishes and report is saved
                updateStatus('Report Ready', 'success');
                
                // Hide any existing reporter processing messages
                hideAgentProcessing('reporter');
                
                // Remove all other reporter status messages that might still be visible
                const allReporterStatusMessages = allLogElements.filter(el => 
                    el.classList.contains('log-agent-reporter') && 
                    el.getAttribute('data-log-type') === 'status'
                );
                
                allReporterStatusMessages.forEach(el => {
                    el.classList.add('opacity-0', 'h-0', 'overflow-hidden', 'my-0', 'py-0', 'transition-all', 'duration-300');
                    setTimeout(() => {
                        try {
                            el.remove();
                            // Remove from allLogElements array
                            const index = allLogElements.indexOf(el);
                            if (index > -1) {
                                allLogElements.splice(index, 1);
                            }
                        } catch (e) {
                            console.error("Error removing reporter status message:", e);
                        }
                    }, 300);
                });
            } 
            else if (log.agent === 'reporter' && log.content.includes('processing')) {
                // Reporter is still processing (before save)
                displayContent(contentContainer, log.content); // Show the processing message
                // Do not add the button yet
            }
            else if (log.agent === 'planner') {
                // Store the planner output for potential plan steps
                window.currentPlannerOutput = log;
                
                // Try to extract the title from planner content if possible
                try {
                    let plannerContent = log.content;
                    if (typeof plannerContent === 'string') {
                        // Try to parse JSON content
                        if (plannerContent.includes('"title"')) {
                            try {
                                const parsedContent = JSON.parse(plannerContent);
                                if (parsedContent && parsedContent.title) {
                                    window.plannerTitle = parsedContent.title;
                                    console.log("Extracted planner title from agent output:", window.plannerTitle);
                                }
                            } catch (e) {
                                // Handle parsing error
                                console.warn("Could not parse planner JSON:", e);
                                
                                // Try regex extraction if JSON parsing fails
                                const titleMatch = plannerContent.match(/Plan Title:\s*([^\n]+)/);
                                if (titleMatch && titleMatch[1]) {
                                    window.plannerTitle = titleMatch[1].trim();
                                    console.log("Extracted planner title via regex:", window.plannerTitle);
                                }
                            }
                        } else {
                            // Try regex extraction for non-JSON content
                            const titleMatch = plannerContent.match(/Plan Title:\s*([^\n]+)/);
                            if (titleMatch && titleMatch[1]) {
                                window.plannerTitle = titleMatch[1].trim();
                                console.log("Extracted planner title via regex:", window.plannerTitle);
                            }
                        }
                    }
                } catch (e) {
                    console.warn("Error extracting planner title:", e);
                }
                
                // Display content normally
                displayContent(contentContainer, log.content);
            }
            else {
                // Display content normally for other agents
                displayContent(contentContainer, log.content);
            }

            // Add the agent container to the message element
            messageElement.appendChild(agentContainer);

            // Hide the current processing status for this agent
            hideAgentProcessing(log.agent);

            // Add the element to the DOM immediately
            outputDiv.appendChild(messageElement);
            allLogElements.push(messageElement);

            // Skip the default append at the end of this function
            return;

        case 'plan_step':
            // If there's a current planner output, append this plan step to it
            const planAgent = log.agent ? log.agent.charAt(0).toUpperCase() + log.agent.slice(1) : 'System';

            // Check if this is the first plan step after a planner output
            if (window.currentPlannerOutput) {
                // Create a container just for the plan steps without duplicating the planner content
                const planStepsContainer = document.createElement('div');
                planStepsContainer.className = 'mt-3 rounded-md bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700';
                
                // Add the "handed off" message before the expandable component
                const handedOffMessage = document.createElement('div');
                handedOffMessage.className = 'px-4 pt-3 pb-2 text-sm italic text-gray-500 dark:text-gray-400';
                handedOffMessage.textContent = 'Planner handed off the following plan to the supervisor:';
                planStepsContainer.appendChild(handedOffMessage);
                
                // Add a heading for plan steps with toggle functionality
                const planStepsHeading = document.createElement('div');
                planStepsHeading.className = 'plan-steps-heading px-4 py-3 bg-gray-50 dark:bg-gray-700/50 rounded-t flex justify-between items-center cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors';
                planStepsHeading.innerHTML = `
                    <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Plan Steps
                    </h4>
                    <svg class="chevron-icon w-5 h-5 text-gray-600 dark:text-gray-400 transition-transform duration-300" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                `;

                // Create a container for all plan steps (collapsed by default)
                const stepsContentContainer = document.createElement('div');
                stepsContentContainer.className = 'plan-steps-container bg-white dark:bg-gray-800 overflow-hidden';
                stepsContentContainer.style.display = 'none'; // Hide by default

                // Create a div for this specific plan step
                const planStepDiv = createPlanStepElement(log);
                stepsContentContainer.appendChild(planStepDiv);

                // Add toggle functionality
                planStepsHeading.addEventListener('click', function() {
                    const chevron = this.querySelector('.chevron-icon');
                    if (stepsContentContainer.style.display === 'none') {
                        stepsContentContainer.style.display = 'block';
                        chevron.style.transform = 'rotate(90deg)';
                    } else {
                        stepsContentContainer.style.display = 'none';
                        chevron.style.transform = 'rotate(0deg)';
                    }
                    
                    // Trigger resize after toggling visibility
                    setTimeout(resizeResultsContainer, 10);
                });

                planStepsContainer.appendChild(planStepsHeading);
                planStepsContainer.appendChild(stepsContentContainer);

                // Find the existing planner output and append the plan steps to it
                const existingPlannerOutput = Array.from(
                    document.querySelectorAll(`[data-log-type="agent_output"][data-log-agent="planner"]`)
                ).pop();

                if (existingPlannerOutput) {
                    // Append plan steps to the existing planner output
                    const contentContainer = existingPlannerOutput.querySelector('.markdown-content')?.parentElement;
                    if (contentContainer) {
                        contentContainer.appendChild(planStepsContainer);
                    } else {
                        existingPlannerOutput.appendChild(planStepsContainer);
                    }
                } else {
                    // If no existing planner output found, add as a new element
                    outputDiv.appendChild(planStepsContainer);
                }

                // Store the steps container for future steps
                window.currentPlanStepsContainer = stepsContentContainer;

                // Clear the current planner output since we've used it
                window.currentPlannerOutput = null;

                // Skip default append
                return;
            }
            else if (window.currentPlanStepsContainer) {
                // This is a subsequent plan step, add it to the existing container
                const planStepDiv = createPlanStepElement(log);
                window.currentPlanStepsContainer.appendChild(planStepDiv);

                // Skip default append
                return;
            }
            else {
                // This is a standalone plan step (shouldn't happen often)
                messageElement.className = 'p-3 mb-2 bg-white dark:bg-gray-800 rounded-md shadow-sm';
                messageElement.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${log.agent ? `agent-icon-${log.agent}` : 'bg-gray-300 dark:bg-gray-700'}">${planAgent.charAt(0)}</div>
                        <div>
                            <div class="text-sm font-semibold">Plan Step</div>
                            <div class="text-xs text-gray-500 dark:text-gray-400">${planAgent} Agent</div>
                        </div>
                    </div>
                `;

                // Append plan step content
                const contentDiv = document.createElement('div');
                contentDiv.className = 'mt-3 pl-10';

                if (typeof log.content === 'object' && log.content !== null) {
                    contentDiv.innerHTML = `
                        <p class="mb-1"><span class="font-medium text-primary-600 dark:text-primary-400">Task:</span> ${sanitizeHTML(log.content.Task || 'N/A')}</p>
                        <p class="mb-1"><span class="font-medium text-primary-600 dark:text-primary-400">Description:</span> ${sanitizeHTML(log.content.Description || 'N/A')}</p>
                        <p><span class="font-medium text-primary-600 dark:text-primary-400">Note:</span> ${sanitizeHTML(log.content.Note || 'N/A')}</p>
                    `;
                } else {
                    contentDiv.innerHTML = `<p>${sanitizeHTML(JSON.stringify(log.content))}</p>`;
                }

                messageElement.appendChild(contentDiv);
            }
            break;

        case 'error':
            messageElement.className = 'p-4 mb-2 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-md border-l-3 border-l-red-500';
            messageElement.innerHTML = `
                <div class="flex items-center">
                    <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>
                    <strong>ERROR:</strong> ${sanitizeHTML(log.content)}
                </div>
            `;
            break;

        default:
            messageElement.className = 'p-3 text-gray-600 dark:text-gray-400';
            messageElement.innerHTML = `<p><em>Unknown log type '${log.type}':</em> ${sanitizeHTML(JSON.stringify(log.content))}</p>`;
    }

    // Set initial state for animation
    messageElement.style.opacity = '0';
    messageElement.style.transform = 'translateY(10px)';
    
    outputDiv.appendChild(messageElement);
    allLogElements.push(messageElement);

    // Apply Motion One animation
    Motion.animate(messageElement, 
        { opacity: 1, transform: 'translateY(0px)' }, 
        { duration: 0.3, easing: "ease-out" }
    );

    // Animate typing dots if present
    const dotsContainer = messageElement.querySelector('.typing-dots-container');
    if (dotsContainer) {
        animateTypingDots(dotsContainer);
    }

    // Force recalculation of container size
    setTimeout(resizeResultsContainer, 50);
}

// Helper function to create a plan step element
function createPlanStepElement(log) {
    const planStepDiv = document.createElement('div');
    planStepDiv.className = 'p-4 border-l-2 border-l-agent-planner border-b border-gray-100 dark:border-gray-800';

    if (typeof log.content === 'object' && log.content !== null) {
        // Get the agent name
        const agentName = log.content.Agent ? log.content.Agent.charAt(0).toUpperCase() + log.content.Agent.slice(1) : '';

        planStepDiv.innerHTML = `
            <div class="w-7 h-7 rounded-full flex items-center justify-center text-sm font-semibold ${log.content.Agent ? `agent-icon-${log.content.Agent}` : 'bg-gray-300'}">${agentName.charAt(0)}</div>
            <h4 class="mt-2 mb-1 text-sm font-medium text-primary-600 dark:text-primary-400">${agentName} Agent</h4>
            <p class="mb-1 text-sm"><span class="font-medium">Task:</span> ${sanitizeHTML(log.content.Task || 'N/A')}</p>
            <p class="mb-1 text-sm"><span class="font-medium">Description:</span> ${sanitizeHTML(log.content.Description || 'N/A')}</p>
            ${log.content.Note ? `<p class="text-sm"><span class="font-medium">Note:</span> ${sanitizeHTML(log.content.Note)}</p>` : ''}
        `;
    } else {
        planStepDiv.innerHTML = `<p class="text-sm">${sanitizeHTML(JSON.stringify(log.content))}</p>`;
    }

    return planStepDiv;
}

// Function to hide agent processing messages
function hideAgentProcessing(agentName) {
    if (!agentName) return;

    const processingMessages = allLogElements.filter(el => 
        el.classList.contains('log-agent-' + agentName) && 
        el.querySelector('.typing-dot')
    );

    processingMessages.forEach(el => {
        // Use Motion One to animate the element before removing it
        Motion.animate(el, 
            { opacity: 0, height: 0, margin: 0, padding: 0 }, 
            { duration: 0.3, easing: "ease-out" }
        ).then(() => {
            try {
                el.remove();
                // Remove from allLogElements array
                const index = allLogElements.indexOf(el);
                if (index > -1) {
                    allLogElements.splice(index, 1);
                }
            } catch (e) {
                console.error("Error removing processing status:", e);
            }
        });
    });
}

// Function to hide supervisor status messages that show "evaluating"
function hideSupervisorEvaluatingMessages() {
    supervisorStatusMessages.forEach(el => {
        // Only hide status messages that include "evaluating"
        if (el.textContent.includes('Supervisor is evaluating')) {
            // Use Motion One to animate the element before removing it
            Motion.animate(el, 
                { opacity: 0, height: 0, margin: 0, padding: 0 }, 
                { duration: 0.3, easing: "ease-out" }
            ).then(() => {
                try {
                    el.remove();
                    // Remove from supervisorStatusMessages array
                    const index = supervisorStatusMessages.indexOf(el);
                    if (index > -1) {
                        supervisorStatusMessages.splice(index, 1);
                    }
                    // Also remove from allLogElements array if present
                    const globalIndex = allLogElements.indexOf(el);
                    if (globalIndex > -1) {
                        allLogElements.splice(globalIndex, 1);
                    }
                } catch (e) {
                    console.error("Error removing supervisor evaluating message:", e);
                }
            });
        }
    });
}

// Function to handle completed agent states
function handleAgentStateTransition(currentAgent, nextAgent) {
    if (!currentAgent || !nextAgent) return;

    // Hide the current agent's processing messages when transitioning to next agent
    hideAgentProcessing(currentAgent);

    // Also hide any status messages indicating the current agent is still working
    const statusMessages = document.querySelectorAll('[class*="status-message-text"], [class*="agent-status"]');
    statusMessages.forEach(el => {
        const text = el.textContent.toLowerCase();
        if ((text.includes(currentAgent.toLowerCase()) && 
             (text.includes('processing') || text.includes('analyzing') || 
              text.includes('gathering') || text.includes('retrieving')))) {
                  
            const container = el.closest('.status-message-container') || 
                              el.closest('.agent-processing') || 
                              el.closest('.log-agent-' + currentAgent);
                              
            if (container) {
                container.style.display = 'none';
            }
        }
    });
}

// Function to handle supervisor messages
function appendSupervisorMessage(content) {
    const messageElement = document.createElement('div');
    messageElement.className = 'mr-2 px-4 py-2 italic text-gray-600 dark:text-gray-400 text-sm flex items-center supervisor-message';
    messageElement.innerHTML = `
        <span class="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 mr-2 supervisor-message-dot"></span>
        <span class="ml-2">${content}</span>
    `;
    
    // Set initial opacity to 0 for animation
    messageElement.style.opacity = '0';
    outputDiv.appendChild(messageElement);
    allLogElements.push(messageElement);
    
    // Use Motion One to animate the fade-in
    Motion.animate(messageElement, 
        { opacity: 1 }, 
        { duration: 0.3, easing: "ease-out" }
    );
    
    // If this is a status message about supervisor evaluating, track it
    if (content.includes('Supervisor is evaluating')) {
        supervisorStatusMessages.push(messageElement);
    }
    
    // If this is a task assignment message, hide any previous evaluating messages
    if (content.includes('Supervisor assigned the following task to')) {
        hideSupervisorEvaluatingMessages();
    }

    // Ensure we're scrolled to the bottom
    outputDiv.scrollTop = outputDiv.scrollHeight;
}

// Function to hide all status messages (for when final report arrives)
function hideAllStatusMessages() {
    statusMessages.forEach(element => {
        // Use Motion One to animate the element before removing it
        Motion.animate(element, 
            { opacity: 0, height: 0, margin: 0, padding: 0 }, 
            { duration: 0.3, easing: "ease-out" }
        ).then(() => {
            try {
                element.remove();
                // Remove from allLogElements array
                const index = allLogElements.indexOf(element);
                if (index > -1) {
                    allLogElements.splice(index, 1);
                }
            } catch (e) {
                console.error("Error removing status message:", e);
            }
        });
    });
    statusMessages = [];
}

submitBtn.addEventListener('click', async () => {
    const query = queryInput.value.trim();
    if (!query) {
        // Shake the input field to indicate it's required
        queryInput.classList.add('shake');
        setTimeout(() => queryInput.classList.remove('shake'), 500);
        return;
    }

    // Check if currentWorkflowConfig is available and reload if necessary
    console.log("Current workflow config before submission:", currentWorkflowConfig);
    if (!currentWorkflowConfig || !currentWorkflowConfig.llm_configs) {
        console.warn("currentWorkflowConfig missing or incomplete, loading from localStorage");
        currentWorkflowConfig = loadWorkflowConfig();
        console.log("Reloaded workflow config:", currentWorkflowConfig);
    }

    // Update button UI to show processing state
    submitBtn.innerHTML = `
        <div class="flex items-center justify-center gap-2 z-10">
            <span>Processing</span>
            <div class="flex gap-1">
                <div class="w-1 h-1 rounded-full bg-white animate-typing-dot typing-dot"></div>
                <div class="w-1 h-1 rounded-full bg-white animate-typing-dot typing-dot"></div>
                <div class="w-1 h-1 rounded-full bg-white animate-typing-dot typing-dot"></div>
            </div>
        </div>
    `;

    // Clear previous output and update status
    outputDiv.innerHTML = '';
    statusMessages = [];
    allLogElements = [];
    supervisorStatusMessages = []; // Reset supervisor status messages
    currentAgentProcessing = null;
    currentSessionId = null; // Reset session ID for the new run
    reportButtonElement = null; // Reset report button reference
    
    // REMOVED report-related variable resets (currentReportId, localStorage, etc.)
    window.plannerTitle = null;

    // Create an initial state message directly inside the results container
    const initialMessage = document.createElement('div');
    initialMessage.className = 'px-4 py-2 italic text-gray-600 dark:text-gray-400 text-sm flex items-center';
    initialMessage.innerHTML = `
        <span class="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 mr-2"></span>
        Starting analysis for query: "${query}"
    `;
    outputDiv.appendChild(initialMessage);

    updateStatus('Initiating Analysis...', 'active');
    submitBtn.disabled = true;

    // Close any existing connection
    if (eventSource) {
        eventSource.close();
    }

    try {
        // Prepare the config payload, ensuring the LLM configs are properly structured
        const configPayload = {
            budget: currentWorkflowConfig.budget || 'low',
            stream_config: { recursion_limit: 150 }
        };
        
        // Only include llm_configs if it exists and has the required properties
        if (currentWorkflowConfig && currentWorkflowConfig.llm_configs) {
            // Create a clean copy with proper capitalization for providers
            configPayload.llm_configs = {
                reasoning: {
                    model: currentWorkflowConfig.llm_configs.reasoning.model,
                    provider: currentWorkflowConfig.llm_configs.reasoning.provider.toUpperCase()
                },
                basic: {
                    model: currentWorkflowConfig.llm_configs.basic.model,
                    provider: currentWorkflowConfig.llm_configs.basic.provider.toUpperCase()
                },
                coding: {
                    model: currentWorkflowConfig.llm_configs.coding.model,
                    provider: currentWorkflowConfig.llm_configs.coding.provider.toUpperCase()
                },
                economic: {
                    model: currentWorkflowConfig.llm_configs.economic.model,
                    provider: currentWorkflowConfig.llm_configs.economic.provider.toUpperCase()
                }
            };
        }
        
        // Log the exact structure being sent to the backend
        console.log("Sending workflow request with config:", JSON.stringify(configPayload));

        // Create the actual request object
        const requestBody = {
            request: { query },
            config: configPayload
        };
        
        console.log("Full request body:", JSON.stringify(requestBody));

        const response = await fetch('/api/run-workflow', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error: ${response.status} - ${errorText}`);
        }

        // Get the response headers to fetch the API URL for SSE and session ID
        const sseUrl = response.headers.get('Content-Location');
        const responseData = await response.json(); // Get session_id from response body
        currentSessionId = responseData.session_id;
        console.log("Received session ID from backend:", currentSessionId);
        
        if (!sseUrl) {
            throw new Error('No streaming URL provided in the response');
        }
        if (!currentSessionId) {
            throw new Error('No session ID provided in the response');
        }

        // Set up the EventSource for streaming
        eventSource = new EventSource(sseUrl);
        console.log(`Establishing EventSource connection to: ${sseUrl}`);
        updateStatus('Connecting to analysis engine...', 'active');

        eventSource.onopen = () => {
            console.log("EventSource connection opened.");
            updateStatus('Analyzing your query...', 'active');
        };

        eventSource.onmessage = async (event) => {
            try {
                const data = JSON.parse(event.data);

                // Log the raw data for debugging
                console.log("Received SSE data:", event.data);

                // Verify session ID matches (optional but good practice)
                if (data.session_id && data.session_id !== currentSessionId) {
                    console.warn(`Received message for different session (${data.session_id}), expected (${currentSessionId}). Ignoring.`);
                    return;
                }

                // Handle specific message types first
                if (data.type === "connection_established") {
                    console.log(`Stream status: ${data.type}`, data.message);
                    currentSessionId = data.session_id; // Reconfirm session ID
                    return;
                }

                if (data.type === "report_status") {
                    console.log(`Report status update: ${data.status}`);
                    if (data.status === 'saved') {
                        updateStatus('Report Ready', 'success');
                        // Hide any existing reporter processing messages
                        hideAgentProcessing('reporter');
                        
                        // Now find the reporter message and potentially add/enable the button
                        const reporterMessages = outputDiv.querySelectorAll('[data-log-agent="reporter"][data-log-type="agent_output"]');
                        const lastReporterMessage = reporterMessages[reporterMessages.length - 1];
                        if (lastReporterMessage) {
                            const contentContainer = lastReporterMessage.querySelector('.mt-3');
                            if (contentContainer && !contentContainer.querySelector('.view-report-button')) {
                                // Create the button container if not already present
                                const reporterContainer = document.createElement('div');
                                reporterContainer.className = 'mt-2 pl-10 flex items-center justify-between';
                                const textDiv = document.createElement('div');
                                textDiv.className = 'text-gray-700 dark:text-gray-300';
                                textDiv.textContent = 'Reporter agent has finished and the report has been saved.'; // Update text
                                reporterContainer.appendChild(textDiv);
                                const buttonDiv = document.createElement('div');
                                buttonDiv.className = 'ml-4';
                                buttonDiv.innerHTML = `
                                    <button onclick="savePageStateAndNavigateToReport()" class="view-report-button px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 text-white text-sm font-medium rounded shadow-sm hover:shadow transform hover:-translate-y-0.5 active:translate-y-0 transition-all duration-300">
                                        View Complete Investment Report
                                    </button>
                                `;
                                reportButtonElement = buttonDiv.querySelector('button');
                                reporterContainer.appendChild(buttonDiv);
                                // Clear previous content and add the new container
                                contentContainer.innerHTML = ''; 
                                contentContainer.appendChild(reporterContainer);
                            }
                        }
                    } else if (data.status === 'error') {
                        appendLogMessage({ type: 'error', content: `Failed to save report: ${data.error_message || 'Unknown error'}` });
                        updateStatus('Error saving report', 'error');
                    }
                    return;
                }
                
                if (data.type === "stream_complete") {
                    console.log(`Stream complete: ${data.type}`, data.message);
                    
                    // Check final report status from backend
                    if (data.report_status === 'saved') {
                        // Ensure UI reflects success if not already
                        if (!statusIndicator.classList.contains('bg-green-50')) {
                             updateStatus('Report Ready', 'success');
                        }
                        // Hide any existing reporter processing messages
                        hideAgentProcessing('reporter');
                         
                        // If button wasn't created by report_status, try adding it now
                        if (!reportButtonElement) {
                            // Find the last reporter message and add the button
                            const reporterMessages = outputDiv.querySelectorAll('[data-log-agent="reporter"][data-log-type="agent_output"]');
                            const lastReporterMessage = reporterMessages[reporterMessages.length - 1];
                            if (lastReporterMessage) {
                                const contentContainer = lastReporterMessage.querySelector('.mt-3');
                                if (contentContainer && !contentContainer.querySelector('.view-report-button')) {
                                     // Add button logic here (similar to report_status handler)
                                     const reporterContainer = document.createElement('div');
                                     reporterContainer.className = 'mt-2 pl-10 flex items-center justify-between';
                                     const textDiv = document.createElement('div');
                                     textDiv.className = 'text-gray-700 dark:text-gray-300';
                                     textDiv.textContent = 'Reporter agent has finished and the report has been saved.'; // Update text
                                     reporterContainer.appendChild(textDiv);
                                     const buttonDiv = document.createElement('div');
                                     buttonDiv.className = 'ml-4';
                                     buttonDiv.innerHTML = `
                                         <button onclick="savePageStateAndNavigateToReport()" class="view-report-button px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 text-white text-sm font-medium rounded shadow-sm hover:shadow transform hover:-translate-y-0.5 active:translate-y-0 transition-all duration-300">
                                             View Complete Investment Report
                                         </button>
                                     `;
                                     reportButtonElement = buttonDiv.querySelector('button');
                                     reporterContainer.appendChild(buttonDiv);
                                     contentContainer.innerHTML = ''; 
                                     contentContainer.appendChild(reporterContainer);
                                }
                            }
                        }
                    } else if (data.report_status === 'error') {
                        updateStatus('Error saving report', 'error');
                    } else if (data.report_status === 'not_generated') {
                        updateStatus('Analysis complete (no report generated)', 'active'); // Use neutral status
                    }
                    
                    // Close the event source
                    eventSource.close();
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<div class="flex items-center justify-center gap-2 z-10"><span>Get Investment Insights</span></div>';
                    // Refresh recent reports list after completion
                    loadRecentReports();
                    return;
                }

                // Process regular log messages
                if (data.logs && Array.isArray(data.logs)) {
                    // Check for report completion before processing logs
                    const hasReportFinished = data.logs.some(log => 
                        log.type === 'agent_output' && 
                        log.agent === 'reporter' && 
                        log.content.includes('report has been saved')
                    );
                    
                    // Filter out any redundant "preparing" messages if the report is finished
                    if (hasReportFinished) {
                        data.logs = data.logs.filter(log => 
                            !(log.type === 'status' && 
                              log.agent === 'reporter' && 
                              log.content.includes('preparing'))
                        );
                    }
                    
                    data.logs.forEach(log => {
                        // Handle agent state transitions
                        if (log.type === 'status' && log.content.includes('Supervisor is evaluating response from')) {
                            const match = log.content.match(/Supervisor is evaluating response from (\w+)\.\.\./);
                            if (match && match[1]) {
                                const agentName = match[1].toLowerCase();
                                handleAgentStateTransition(agentName, 'supervisor');
                            }
                        }

                        // When supervisor assigns a task to a new agent
                        if (log.type === 'status' && log.content.includes('Supervisor assigned the following task to')) {
                            const lastAgent = data.last_agent || null;
                            const nextAgent = data.next || null;
                            
                            // Hide any previous supervisor evaluating messages when supervisor assigns a task
                            hideSupervisorEvaluatingMessages();
                            
                            if (lastAgent && nextAgent && lastAgent !== nextAgent) {
                                handleAgentStateTransition(lastAgent, nextAgent);
                            }
                        }

                        // Handle different log types
                        if (log.type === 'status' &&
                            (log.content.includes('Supervisor is evaluating') ||
                             log.content.includes('Supervisor assigned'))) {
                            appendSupervisorMessage(log.content);
                        } else {
                            appendLogMessage(log);
                        }
                    });
                    
                    // Update header status indicator based on the last status log
                    const lastStatusLog = data.logs.slice().reverse().find(log => log.type === 'status');
                    if (lastStatusLog) {
                        // Only update if not already success or error
                        if (!statusIndicator.classList.contains('bg-green-50') && !statusIndicator.classList.contains('bg-red-50')) {
                            updateStatus(lastStatusLog.content, 'active');
                        }
                    }

                    // Ensure scrolling to bottom
                    outputDiv.scrollTop = outputDiv.scrollHeight;
                } else if (data.error) {
                    console.error("Received error from stream:", data.error);
                    
                    // Handle specific errors (keep JSON decode error handling)
                    if (data.details && data.details.includes('invalid escaped character in string')) {
                        console.warn("JSON decode error detected.");
                        appendLogMessage({ 
                            type: 'error', 
                            content: `Data format error: The system encountered an issue with special characters.` 
                        });
                        if (data.type === 'stream_error') {
                            eventSource.close();
                            updateStatus('Error', 'error');
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = '<div class="flex items-center justify-center gap-2 z-10"><span>Get Investment Insights</span></div>';
                        } else if (data.type === 'chunk_error') {
                            console.warn("Continuing stream despite chunk error");
                            updateStatus('Processing with warnings', 'active');
                        }
                    } else {
                        // Handle other errors
                        appendLogMessage({ type: 'error', content: `Analysis Error: ${data.details || data.error}` });
                        eventSource.close();
                        updateStatus('Error', 'error');
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<div class="flex items-center justify-center gap-2 z-10"><span>Get Investment Insights</span></div>';
                    }
                } else {
                    // Handle unexpected data format
                    console.warn("Received unexpected data format:", data);
                    appendLogMessage({
                        type: 'error',
                        content: `Received unexpected data format. Check console for details.`
                    });
                }

                // Always resize the container after appending messages
                resizeResultsContainer();
            } catch (error) {
                console.error('Error parsing or processing SSE message:', error, "Raw data:", event.data);
                appendLogMessage({ type: 'error', content: `Error processing message: ${error.message}. See console for details.` });
            }
        };

        eventSource.onerror = (error) => {
            console.error('EventSource error:', error);
            // Avoid double error message if connection closed after final report
            if (!statusIndicator.classList.contains('success') && !statusIndicator.classList.contains('error')) {
                appendLogMessage({
                    type: 'error',
                    content: 'Connection error or stream ended unexpectedly. Try refreshing the page.'
                });
                updateStatus('Connection Error', 'error');
            }
            eventSource.close();
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<div class="flex items-center justify-center gap-2 z-10"><span>Get Investment Insights</span></div>';
        };
    } catch (error) {
        console.error('Error:', error);
        appendLogMessage({ type: 'error', content: `Failed to start analysis: ${error.message}` });
        updateStatus('Error', 'error');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<div class="flex items-center justify-center gap-2 z-10"><span>Get Investment Insights</span></div>';
        if (eventSource) eventSource.close(); // Ensure cleanup
    }
});

// Helper function to update status with visual indicator
function updateStatus(message, status) {
    // Update status in the header
    const statusIndicatorText = statusIndicator.querySelector('span:not(.status-dot)');
    statusIndicatorText.textContent = message;

    // Remove all status classes
    statusIndicator.classList.remove('bg-primary-50', 'bg-green-50', 'bg-red-50', 'text-primary-600', 'text-green-600', 'text-red-600', 'bg-gray-100', 'text-gray-600');

    const statusIndicatorDot = statusIndicator.querySelector('.status-dot');
    statusIndicatorDot.classList.remove('bg-primary-500', 'bg-green-500', 'bg-red-500', 'bg-gray-400', 'animate-pulse');

    // Add appropriate class based on status
    if (status === 'active' || status === 'connected') {
        statusIndicator.classList.add('bg-primary-50', 'dark:bg-primary-900/20', 'text-primary-600', 'dark:text-primary-400');
        statusIndicatorDot.classList.add('bg-primary-500');
        
        // Animate the pulse effect with Motion One
        Motion.animate(
            statusIndicatorDot, 
            { 
                scale: [0.8, 1.2, 0.8],
                opacity: [0.8, 1, 0.8]
            }, 
            { 
                duration: 2,
                repeat: Infinity,
                easing: "ease-in-out"
            }
        );
    } else if (status === 'success') {
        statusIndicator.classList.add('bg-green-50', 'dark:bg-green-900/20', 'text-green-600', 'dark:text-green-400');
        statusIndicatorDot.classList.add('bg-green-500');
        
        // Stop any existing animation
        Motion.animate(statusIndicatorDot, { scale: 1, opacity: 1 });
    } else if (status === 'error') {
        statusIndicator.classList.add('bg-red-50', 'dark:bg-red-900/20', 'text-red-600', 'dark:text-red-400');
        statusIndicatorDot.classList.add('bg-red-500');
        
        // Stop any existing animation
        Motion.animate(statusIndicatorDot, { scale: 1, opacity: 1 });
    } else {
        statusIndicator.classList.add('bg-gray-100', 'dark:bg-gray-800', 'text-gray-600', 'dark:text-gray-400');
        statusIndicatorDot.classList.add('bg-gray-400');
        
        // Stop any existing animation
        Motion.animate(statusIndicatorDot, { scale: 1, opacity: 1 });
    }
}

// Allow submitting by pressing Enter in the input field
queryInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !submitBtn.disabled) {
        submitBtn.click();
    }
});

// Keyboard shortcut: Ctrl+Enter or Cmd+Enter to submit
document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !submitBtn.disabled) {
        submitBtn.click();
    }
});

// Focus on the input field when the page loads
window.addEventListener('load', () => {
    queryInput.focus();
});

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

// Function to resize the results container based on content
function resizeResultsContainer() {
    const resultsContainer = document.querySelector('.results-content');
    if (!resultsContainer) {
        return;
    }

    // Get the current scroll position to restore it later
    const scrollTop = resultsContainer.scrollTop;

    // Reset height to auto to measure real content height
    resultsContainer.style.height = 'auto';
    resultsContainer.style.minHeight = '';

    // Get the scrollHeight of the content
    const contentHeight = resultsContainer.scrollHeight;
    const minHeight = 550;

    // Set the height to the maximum of content height or minimum height
    const newHeight = Math.max(contentHeight, minHeight);
    resultsContainer.style.minHeight = `${newHeight}px`;
    
    // Restore scroll position
    resultsContainer.scrollTop = scrollTop;
}

// Observer to resize container when content changes
if ('ResizeObserver' in window) {
    const resizeObserver = new ResizeObserver((entries) => {
        resizeResultsContainer();
    });

    // Start observing the results content when it's available
    const resultsContent = document.querySelector('.results-content');
    if (resultsContent) {
        resizeObserver.observe(resultsContent);
    }
}

// Setup example queries
function setExampleQuery(query) {
    queryInput.value = query;
    queryInput.focus();
}

// Function to save state and navigate to report using session_id
function savePageStateAndNavigateToReport() {
    if (!currentSessionId) {
        console.error("Cannot navigate to report: Session ID is missing.");
        showToast("Error: Could not determine the report session.");
        return;
    }
    
    // Save current page state to localStorage before navigating
    localStorage.setItem('returnFromReport', 'true');
    localStorage.setItem('reportQuery', queryInput.value.trim());
    localStorage.setItem('scrollPosition', outputDiv.scrollTop);
    localStorage.setItem('cachedOutputHtml', outputDiv.innerHTML);
    localStorage.setItem('reportSessionId', currentSessionId); // Save session ID
    
    // Save status indicator state
    localStorage.setItem('statusText', statusIndicator.querySelector('span:not(.status-dot)').textContent);
    localStorage.setItem('statusClass',
        statusIndicator.classList.contains('bg-green-50') ? 'success' :
        statusIndicator.classList.contains('bg-primary-50') ? 'active' :
        statusIndicator.classList.contains('bg-red-50') ? 'error' : '');
    
    // Navigate to the report page using session_id
    window.location.href = `/report?session_id=${currentSessionId}`;
}

// Function to load recent reports from MongoDB
function loadRecentReports() {
    const recentReportsList = document.getElementById('recent-reports-list');

    if (!recentReportsList) {
        console.error('Recent reports list element not found');
        return Promise.reject(new Error('Recent reports list element not found'));
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

    // Fetch recent reports from API and return the promise
    return fetch('/api/recent-reports?limit=5')
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
                return data;
            }

            // Clear the list
            recentReportsList.innerHTML = '';

            // Add each report to the list using session_id for the link
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
                // Use session_id in the href
                reportItem.innerHTML = `
                    <a href="/report?session_id=${report.session_id}" class="flex items-center p-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 transition-colors">
                        <span class="mr-3"><i class="fa-regular fa-file-lines"></i></span>
                        <div class="flex flex-col">
                            <span class="text-sm">${shortTitle}</span>
                            <span class="text-xs text-gray-500">${reportDate}</span>
                        </div>
                    </a>
                `;
                recentReportsList.appendChild(reportItem);
            });
            
            return data;
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
            throw error; // Re-throw so calling code knows it failed
        });
} 