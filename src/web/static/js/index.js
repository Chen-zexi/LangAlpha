// JavaScript for the index.html page

document.addEventListener('DOMContentLoaded', function() {
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

    // Check if we're returning from report page
    const isReturningFromReport = checkReturnFromReport();

    // Only load recent reports if not returning from report page
    // This prevents overwriting the cached output
    if (!isReturningFromReport) {
        console.log("Loading recent reports from MongoDB...");
        loadRecentReports();
    } else {
        // Remove loading indicator if present when returning from report
        const recentReportsList = document.getElementById('recent-reports-list');
        if (recentReportsList && recentReportsList.innerHTML.includes('Loading recent reports')) {
            // Display an empty state instead of constant loading
            recentReportsList.innerHTML = `
                <li class="mb-1">
                    <div class="flex items-center p-3 rounded-md text-gray-700 dark:text-gray-300">
                        <span class="mr-3">📝</span>
                        Recent reports
                    </div>
                </li>
            `;
        }
    }
});

const submitBtn = document.getElementById('submit-btn');
const queryInput = document.getElementById('query');
const outputDiv = document.getElementById('output');
const statusIndicator = document.getElementById('status-indicator');

let eventSource = null;
let currentAgentProcessing = null;
let statusMessages = [];
let allLogElements = [];

// Add global variables to track planner output and steps
window.currentPlannerOutput = null;
window.currentPlanStepsContainer = null;
window.plannerTitle = null; // Track the planner title

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

            // Re-attach event listeners to interactive elements if needed
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
                const arrow = this.querySelector('span');
                const isHidden = container.style.display === 'none';
                container.style.display = isHidden ? 'block' : 'none';
                arrow.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
            });
        }
    });

    // Reattach view report button functionality
    const reportButtons = outputDiv.querySelectorAll('button[onclick*="window.location.href=\'report.html\'"]');
    reportButtons.forEach(button => {
        button.onclick = savePageStateAndNavigate;
    });
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

// Function to display text directly without typing effect
function displayText(element, text) {
    element.innerHTML += sanitizeHTML(text);
    resizeResultsContainer();
}

// Function to format and append log messages
function appendLogMessage(log) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('log-message', 'animate-fade-in');

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
        case 'separator':
            messageElement.innerHTML = `<hr class="border-t border-gray-100 dark:border-gray-800 my-1 opacity-40 ${log.content.startsWith('=') ? 'border-t-2' : ''}">`;
            break;

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
                        <div class="ml-2 flex gap-1">
                            <div class="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-typing-dot typing-dot"></div>
                            <div class="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-typing-dot typing-dot"></div>
                            <div class="w-1 h-1 rounded-full bg-gray-400 dark:bg-gray-500 animate-typing-dot typing-dot"></div>
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
                        existingProcessing.classList.add('opacity-0', 'h-0', 'overflow-hidden', 'my-0', 'py-0');
                        setTimeout(() => {
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
                        }, 300);
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

            // Special handling for reporter agent - always display the report button when it finishes
            if (log.agent === 'reporter' && log.content.includes('finished the task')) {
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
                buttonDiv.innerHTML = `
                    <button onclick="savePageStateAndNavigateToReport()" class="px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 text-white text-sm font-medium rounded shadow-sm hover:shadow transform hover:-translate-y-0.5 active:translate-y-0 transition-all duration-300">
                        View Complete Investment Report
                    </button>
                `;
                reporterContainer.appendChild(buttonDiv);

                // Replace the standard content container with our custom one
                contentContainer.appendChild(reporterContainer);

                // Update status to success when reporter finishes
                updateStatus('Report Ready', 'success');

                // Generate a simple report from the agent outputs if one doesn't exist
                // and we haven't already created or received a final report
                if (!window.finalReportGenerated && !window.finalReportContent && !window.currentReportId) {
                    window.finalReportGenerated = true;

                    // Get all content from agent outputs
                    const allAgentOutputs = Array.from(document.querySelectorAll('[data-log-type="agent_output"]'))
                        .map(el => {
                            const agentName = el.getAttribute('data-log-agent') || 'unknown';
                            const content = el.querySelector('.markdown-content')?.innerText || el.innerText || '';
                            return `## ${agentName.charAt(0).toUpperCase() + agentName.slice(1)} Analysis\n\n${content}\n\n`;
                        })
                        .join('\n');

                    const reportContent = `# Investment Analysis Report\n\n${allAgentOutputs}\n\n*Generated on ${new Date().toLocaleString()}*`;
                    
                    // Save the report to MongoDB directly only if we don't already have a report ID
                    if (!window.currentReportId) {
                        fetch('/api/create-report', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                content: reportContent,
                                title: `Analysis: ${queryInput.value.trim()}`,
                                planner_title: window.plannerTitle, // Pass planner title if available
                                metadata: {
                                    query: queryInput.value.trim()
                                }
                            }),
                        })
                        .then(response => response.json())
                        .then(data => {
                            console.log('Report saved to MongoDB:', data);
                            // Store report ID for navigation
                            window.currentReportId = data.report_id;
                            // Refresh recent reports list
                            loadRecentReports();
                        })
                        .catch(error => console.error('Error saving report:', error));
                    } else {
                        console.log('Report already exists with ID:', window.currentReportId);
                    }
                } else {
                    console.log('Report generation skipped - already generated');
                }
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
                    <span class="chevron-icon inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-200 dark:bg-gray-700 transition-transform duration-300">&#62;</span>
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

        case 'final_report':
            // Hide all status messages when final report arrives
            hideAllStatusMessages();

            // Save the final report content but don't display directly
            window.finalReportContent = log.content;
            
            // Set that we have a report in memory
            window.finalReportGenerated = true;

            // Save to MongoDB via API only if we don't already have a report ID
            if (!window.currentReportId) {
                fetch('/api/create-report', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        content: log.content,
                        title: `Analysis: ${queryInput.value.trim()}`,
                        planner_title: window.plannerTitle, // Pass planner title if available
                        metadata: {
                            query: queryInput.value.trim()
                        }
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Final report saved to MongoDB:', data);
                    // Store report ID for navigation
                    window.currentReportId = data.report_id;
                    // Refresh recent reports list
                    loadRecentReports();
                })
                .catch(error => console.error('Error saving final report:', error));
            } else {
                console.log('Report already exists with ID:', window.currentReportId);
            }

            // Update status to success
            updateStatus('Report Ready', 'success');

            // Skip default append - we won't show the report directly anymore
            return;

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

    outputDiv.appendChild(messageElement);
    allLogElements.push(messageElement);

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
                console.error("Error removing processing status:", e);
            }
        }, 300);
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
    messageElement.className = 'px-4 py-2 italic text-gray-600 dark:text-gray-400 text-sm flex items-center';
    messageElement.innerHTML = `
        <span class="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 mr-2"></span>
        ${content}
    `;
    outputDiv.appendChild(messageElement);

    // Ensure we're scrolled to the bottom
    outputDiv.scrollTop = outputDiv.scrollHeight;
}

// Helper function to hide all status messages (for when final report arrives)
function hideAllStatusMessages() {
    statusMessages.forEach(element => {
        element.classList.add('opacity-0', 'h-0', 'overflow-hidden', 'my-0', 'py-0', 'transition-all', 'duration-300');
        setTimeout(() => {
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
        }, 300);
    });
    statusMessages = [];
}

// Modified function to handle streaming messages - all inside the container
async function formatChunkForRendering(chunk) {
    const messagesData = chunk.data.messages || [];
    const nextAgent = chunk.data.next || null;
    const lastAgent = chunk.data.last_agent || null;
    const finalReport = chunk.data.final_report || null;
    
    // Store planner title if available
    if (chunk.data.planner_title) {
        window.plannerTitle = chunk.data.planner_title;
        console.log("Stored planner title:", window.plannerTitle);
    }

    // Use the latest message if available
    const latestMessage = messagesData.length > 0 ? messagesData[messagesData.length - 1] : null;

    // Handle status messages
    if (nextAgent) {
        let statusMessage = `Waiting for ${nextAgent}...`; // Default message

        if (nextAgent === "planner") {
            statusMessage = 'Planner is developing an investment analysis strategy...';
        } else if (nextAgent === "supervisor") {
            statusMessage = `Supervisor is evaluating response from ${lastAgent || "previous agent"}...`;
        } else if (nextAgent === "researcher") {
            statusMessage = 'Researcher is gathering financial information...';
        } else if (nextAgent === "coder") {
            statusMessage = 'Coder is analyzing data patterns...';
        } else if (nextAgent === "market") {
            statusMessage = 'Market agent is retrieving market data and trends...';
        } else if (nextAgent === "browser") {
            statusMessage = 'Browser agent is searching for current financial news...';
        } else if (nextAgent === "analyst") {
            statusMessage = 'Analyst is synthesizing information and forming insights...';
        } else if (nextAgent === "reporter" && lastAgent !== "reporter") {
            statusMessage = 'Reporter is preparing your investment analysis report...';
        } else if (nextAgent === "reporter" && lastAgent === "reporter") {
            statusMessage = 'Reporter is finalizing the investment insights...';
        }

        // Create supervisor message inside the container
        appendSupervisorMessage(statusMessage);
    }

    // Handle agent messages
    if (latestMessage) {
        const agent_name = latestMessage.name;
        const content_str = latestMessage.content;

        if (agent_name && content_str) {
            try {
                const content = typeof content_str === 'string' ? JSON.parse(content_str) : content_str;

                // Handle different agent types
                if (agent_name === "supervisor") {
                    if (typeof content === 'object' && content && content.task) {
                        appendSupervisorMessage(`Supervisor assigned the following task to ${nextAgent || 'an agent'}: ${content.task}`);
                    }
                } else {
                    // Handle other agent outputs through the regular message renderer
                    appendLogMessage({
                        type: 'agent_output',
                        agent: agent_name,
                        content: typeof content_str === 'string' ? content_str : JSON.stringify(content_str)
                    });
                }
            } catch (e) {
                // Handle plain text content
                if (agent_name === "supervisor") {
                    appendSupervisorMessage(`Supervisor: ${content_str}`);
                } else {
                    appendLogMessage({
                        type: 'agent_output',
                        agent: agent_name,
                        content: content_str
                    });
                }
            }
        }
    }

    // Handle final report if present
    if (finalReport) {
        appendLogMessage({ type: 'final_report', content: finalReport });
    }

    // Ensure we're scrolled to the bottom after adding content
    outputDiv.scrollTop = outputDiv.scrollHeight;
}

submitBtn.addEventListener('click', async () => {
    const query = queryInput.value.trim();
    if (!query) {
        // Shake the input field to indicate it's required
        queryInput.classList.add('shake');
        setTimeout(() => queryInput.classList.remove('shake'), 500);
        return;
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
    currentAgentProcessing = null;

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
        // Set up the POST request with EventSource
        const response = await fetch('/api/run-workflow', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                request: { query },
                config: {
                    stream_config: { recursion_limit: 150 }
                }
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error: ${response.status} - ${errorText}`);
        }

        // Get the response headers to fetch the API URL for SSE
        const sseUrl = response.headers.get('Content-Location');
        if (!sseUrl) {
            throw new Error('No streaming URL provided in the response');
        }

        // Set up the EventSource for streaming
        eventSource = new EventSource(sseUrl);
        console.log(`Establishing EventSource connection to: ${sseUrl}`);
        updateStatus('Connecting to analysis engine...', 'active');

        eventSource.onopen = () => {
            console.log("EventSource connection opened.");
            updateStatus('Analyzing your query...', 'active');
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                // Log the raw data for debugging
                console.log("Received SSE data:", event.data);

                // Special handling for connection established messages
                if (data.type === "connection_established" || data.type === "stream_complete") {
                    // Just log these control messages, no need to display them
                    console.log(`Stream status: ${data.type}`, data.message);
                    return;
                }

                if (data.logs && Array.isArray(data.logs)) {
                    // Process each log directly inside the container
                    data.logs.forEach(log => {
                        // Handle agent state transitions
                        if (log.type === 'status' && log.content.includes('Supervisor is evaluating response from')) {
                            // Extract the agent name from "Supervisor is evaluating response from X..."
                            const match = log.content.match(/Supervisor is evaluating response from (\w+)\.\.\./);
                            if (match && match[1]) {
                                const agentName = match[1].toLowerCase();
                                handleAgentStateTransition(agentName, 'supervisor');
                            }
                        }

                        // When supervisor assigns a task to a new agent, mark the previous agent as completed
                        if (log.type === 'status' && log.content.includes('Supervisor assigned the following task to')) {
                            // If we know the last agent, mark it as completed
                            const lastAgent = data.last_agent || null;
                            const nextAgent = data.next || null;

                            if (lastAgent && nextAgent && lastAgent !== nextAgent) {
                                handleAgentStateTransition(lastAgent, nextAgent);
                            }
                        }

                        if (log.type === 'status' &&
                            (log.content.includes('Supervisor is evaluating') ||
                             log.content.includes('Supervisor assigned'))) {
                            // Handle supervisor messages specially
                            appendSupervisorMessage(log.content);
                        } else {
                            // Handle all other messages normally
                            appendLogMessage(log);
                        }
                    });

                    // Check if the last log in this chunk is the final report
                    const lastLog = data.logs[data.logs.length - 1];
                    if (lastLog && lastLog.type === 'final_report') {
                        console.log("Final report received. Closing connection.");
                        eventSource.close();
                        updateStatus('Report Ready', 'success');
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<div class="flex items-center justify-center gap-2 z-10"><span>Get Investment Insights</span></div>';

                        // Store the final report in localStorage but don't redirect
                        localStorage.setItem('finalReport', lastLog.content);
                        localStorage.setItem('reportQuery', queryInput.value.trim());
                    }

                    // Update status indicator in header only
                    const lastStatusLog = data.logs.slice().reverse().find(log => log.type === 'status');
                    if (lastStatusLog) {
                        updateStatus(lastStatusLog.content, 'active');
                    }

                    // Ensure scrolling to bottom after adding content
                    outputDiv.scrollTop = outputDiv.scrollHeight;
                } else if (data.error) {
                    console.error("Received error from stream:", data.error);
                    appendLogMessage({ type: 'error', content: `Analysis Error: ${data.details || data.error}` });
                    eventSource.close();
                    updateStatus('Error', 'error');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<div class="flex items-center justify-center gap-2 z-10"><span>Get Investment Insights</span></div>';
                } else {
                    // If data doesn't match expected format, show error and debug info
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

        // Add these improved error handlers
        eventSource.onerror = (error) => {
            console.error('EventSource error:', error);
            // Avoid double error message if connection closed after final report
            if (!statusIndicator.classList.contains('success')) {
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
        statusIndicatorDot.classList.add('bg-primary-500', 'animate-pulse');
    } else if (status === 'success') {
        statusIndicator.classList.add('bg-green-50', 'dark:bg-green-900/20', 'text-green-600', 'dark:text-green-400');
        statusIndicatorDot.classList.add('bg-green-500');
    } else if (status === 'error') {
        statusIndicator.classList.add('bg-red-50', 'dark:bg-red-900/20', 'text-red-600', 'dark:text-red-400');
        statusIndicatorDot.classList.add('bg-red-500');
    } else {
        statusIndicator.classList.add('bg-gray-100', 'dark:bg-gray-800', 'text-gray-600', 'dark:text-gray-400');
        statusIndicatorDot.classList.add('bg-gray-400');
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

    // Reset height to auto to measure real content height
    resultsContainer.style.height = 'auto';

    // Get the scrollHeight of the content
    const contentHeight = resultsContainer.scrollHeight;
    const minHeight = 400;

    // Set the height to the maximum of content height or minimum height
    resultsContainer.style.minHeight = `${Math.max(contentHeight, minHeight)}px`;
}

// Setup example queries
function setExampleQuery(query) {
    queryInput.value = query;
    queryInput.focus();
}

// Observer to resize container when content changes
if ('ResizeObserver' in window) {
    const resizeObserver = new ResizeObserver(() => {
        resizeResultsContainer();
    });

    // Start observing the results content
    const resultsContent = document.querySelector('.results-content');
    if (resultsContent) {
        resizeObserver.observe(resultsContent);
    }
}

function savePageStateAndNavigate() {
    // Save current page state
    localStorage.setItem('returnFromReport', 'true');
    localStorage.setItem('reportQuery', queryInput.value.trim());

    // Save the current scroll position
    localStorage.setItem('scrollPosition', outputDiv.scrollTop);

    // Cache the entire output content
    localStorage.setItem('cachedOutputHtml', outputDiv.innerHTML);

    // Save information about all log elements
    const logElementsInfo = allLogElements.map(el => {
        return {
            className: el.className,
            type: el.getAttribute('data-log-type') || '',
            agent: el.getAttribute('data-log-agent') || ''
        };
    });
    localStorage.setItem('cachedLogElements', JSON.stringify(logElementsInfo));

    // Save current status indicator state
    localStorage.setItem('statusText', statusIndicator.querySelector('span:not(.status-dot)').textContent);
    localStorage.setItem('statusClass',
        statusIndicator.classList.contains('bg-green-50') ? 'success' :
        statusIndicator.classList.contains('bg-primary-50') ? 'active' :
        statusIndicator.classList.contains('bg-red-50') ? 'error' : '');

    // Redirect to report page
    window.location.href = 'report.html';
}

// Function to save state and navigate to report
function savePageStateAndNavigateToReport() {
    // Save current page state to localStorage before navigating
    localStorage.setItem('returnFromReport', 'true');
    localStorage.setItem('reportQuery', queryInput.value.trim());
    localStorage.setItem('scrollPosition', outputDiv.scrollTop);
    localStorage.setItem('cachedOutputHtml', outputDiv.innerHTML);
    
    // Save status indicator state
    localStorage.setItem('statusText', statusIndicator.querySelector('span:not(.status-dot)').textContent);
    localStorage.setItem('statusClass',
        statusIndicator.classList.contains('bg-green-50') ? 'success' :
        statusIndicator.classList.contains('bg-primary-50') ? 'active' :
        statusIndicator.classList.contains('bg-red-50') ? 'error' : '');
    
    if (window.currentReportId) {
        // Navigate to the report page with the stored report ID
        window.location.href = `/report?report_id=${window.currentReportId}`;
    } else {
        // Fallback: Generate a report from agent outputs
        console.error("No report ID available. Generating fallback report...");

        // Get all content from agent outputs
        const allAgentOutputs = Array.from(document.querySelectorAll('[data-log-type="agent_output"]'))
            .map(el => {
                const agentName = el.getAttribute('data-log-agent') || 'unknown';
                const content = el.querySelector('.markdown-content')?.innerText || el.innerText || '';
                return `## ${agentName.charAt(0).toUpperCase() + agentName.slice(1)} Analysis\n\n${content}\n\n`;
            })
            .join('\n');

        const reportContent = `# Investment Analysis Report\n\n${allAgentOutputs}\n\n*Generated on ${new Date().toLocaleString()}*`;

        // Save the report to MongoDB only if we don't already have a report ID
        if (!window.currentReportId) {
            fetch('/api/create-report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: reportContent,
                    title: `Analysis: ${queryInput.value.trim()}`,
                    planner_title: window.plannerTitle, // Pass planner title if available
                    metadata: {
                        query: queryInput.value.trim()
                    }
                }),
            })
            .then(response => response.json())
            .then(data => {
                console.log('Fallback report saved to MongoDB:', data);
                // Navigate to the report page with the new report ID
                if (data.report_id) {
                    window.location.href = `/report?report_id=${data.report_id}`;
                } else {
                    alert('Error: No report ID returned from server');
                }
            })
            .catch(error => {
                console.error('Error saving fallback report:', error);
                alert('Error saving report. Please try again.');
            });
        } else {
            console.log('Report already exists with ID:', window.currentReportId);
            window.location.href = `/report?report_id=${window.currentReportId}`;
        }
    }
}

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
                const queryText = report.metadata && report.metadata.query
                    ? report.metadata.query
                    : (report.title || 'Investment Analysis');

                const shortQuery = queryText.length > 30
                    ? queryText.substring(0, 30) + '...'
                    : queryText;

                const reportItem = document.createElement('li');
                reportItem.className = 'mb-1';
                reportItem.innerHTML = `
                    <a href="/report?report_id=${report._id}" class="flex items-center p-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 transition-colors">
                        <span class="mr-3">📄</span>
                        <div class="flex flex-col">
                            <span class="text-sm">${shortQuery}</span>
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