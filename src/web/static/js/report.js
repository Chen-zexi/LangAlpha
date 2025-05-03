// JavaScript for the report.html page

document.addEventListener('DOMContentLoaded', () => {
    // Configure marked.js for consistent rendering with index.js
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
    
    // Get session ID from URL query parameters
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    // DOM Elements
    const reportTitle = document.getElementById('report-title');
    const reportQuery = document.getElementById('report-query');
    const reportTimestamp = document.getElementById('report-timestamp');
    const sessionIdDisplay = document.getElementById('session-id');
    const reportContent = document.getElementById('report-content');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessage = document.getElementById('error-message');
    const backButton = document.getElementById('back-button');
    const downloadButton = document.getElementById('download-button');
    
    // Load report data if a session ID is provided
    if (sessionId) {
        loadReport(sessionId);
    } else {
        showError('No session ID provided. Please return to the main page and select a report.');
    }
    
    // Event listeners
    if (backButton) {
        backButton.addEventListener('click', () => {
            // Return to the main page
            window.location.href = '/';
        });
    }
    
    if (downloadButton) {
        downloadButton.addEventListener('click', () => {
            // Use html2pdf.js to generate a PDF containing only the report content
            const reportContentElement = document.getElementById('report-content');
            
            if (!reportContentElement || reportContentElement.innerHTML.trim() === '') {
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
            const pdfReportTitle = document.getElementById('report-title').textContent || 'Investment Report';
            const fileName = pdfReportTitle.replace(/[^a-z0-9]/gi, '_').toLowerCase() + '.pdf';
            
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
            html2pdf()
                .from(reportContentElement)
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
                if (response.status === 404) {
                    throw new Error('Report not found for this session.');
                } else {
                    throw new Error(`Failed to load report: ${response.statusText}`);
                }
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
    
    // Helper function to diagnose markdown content issues
    function diagnoseMarkdownIssues(content) {
        console.group('Markdown Diagnostics');
        
        // Check for common markdown elements
        const hasHeadings = /^#+\s+.+$/m.test(content);
        console.log('Contains headings:', hasHeadings);
        
        const hasBoldOrItalic = /(\*\*|\*|__|\b_\b).+(\*\*|\*|__|\b_\b)/m.test(content);
        console.log('Contains bold/italic:', hasBoldOrItalic);
        
        const hasLists = /^\s*[\-\*\+]\s+.+$/m.test(content);
        console.log('Contains lists:', hasLists);
        
        // Improved table detection with more patterns
        const tablePattern1 = /^\|.+\|$/m.test(content);
        const tablePattern2 = /^\|\s*[-:]+\s*\|$/m.test(content);
        const tablePattern3 = /\| +[^|]+ +\|/m.test(content);
        const hasTables = tablePattern1 || tablePattern2 || tablePattern3;
        console.log('Contains tables:', hasTables);
        console.log('- Table pattern 1 (header row):', tablePattern1);
        console.log('- Table pattern 2 (separator row):', tablePattern2);
        console.log('- Table pattern 3 (content row):', tablePattern3);
        
        const hasCodeBlocks = /```[\s\S]+?```/m.test(content);
        console.log('Contains code blocks:', hasCodeBlocks);
        
        // Check for code block wrapping the whole content
        const isWrappedInCodeBlock = /^```[\s\S]+```$/m.test(content);
        console.log('Content is wrapped in code block:', isWrappedInCodeBlock);
        
        // Check for special characters that might cause issues
        const hasSpecialChars = /[<>&'"\\]/.test(content);
        console.log('Contains potentially problematic special chars:', hasSpecialChars);
        
        // Check for possibly escaped characters (JSON encoding issues)
        const hasEscapedChars = /\\[nrt"']/.test(content);
        console.log('Contains escaped characters:', hasEscapedChars);
        
        // Check for possibly incomplete markdown
        const hasIncompleteMarkdown = (
            /\*\*[^*]+$/.test(content) || // Unclosed bold
            /\*[^*]+$/.test(content) ||   // Unclosed italic
            /```[^`]+$/.test(content)     // Unclosed code block
        );
        console.log('Contains potentially incomplete markdown:', hasIncompleteMarkdown);
        
        // See if there are any HTML-like tags that might be causing problems
        const hasHtmlLikeTags = /<[a-z]+(\s+[a-z]+="[^"]*")*\s*>/i.test(content);
        console.log('Contains HTML-like tags:', hasHtmlLikeTags);
        
        console.groupEnd();
        
        return {
            hasHeadings,
            hasBoldOrItalic,
            hasLists,
            hasTables,
            hasCodeBlocks,
            isWrappedInCodeBlock,
            hasSpecialChars,
            hasEscapedChars,
            hasIncompleteMarkdown,
            hasHtmlLikeTags
        };
    }
    
    // Helper function to fix common markdown issues often seen with different models
    function preprocessMarkdown(content) {
        if (!content) return content;
        
        // Fix common issues with markdown content from different models
        let processed = content;
        
        // Remove markdown code block wrapping if it exists - handle multiple variants
        const markdownCodeBlockPattern = /^```(markdown|md)?\s+([\s\S]+?)\s+```$/;
        const codeBlockMatch = processed.match(markdownCodeBlockPattern);
        
        if (codeBlockMatch) {
            console.log('Found entire content wrapped in markdown code block, unwrapping it');
            processed = codeBlockMatch[2] || codeBlockMatch[1];
        }
        
        // Also check for any nested markdown blocks
        const nestedMarkdownPattern = /```(markdown|md)\s+([\s\S]+?)\s+```/g;
        if (nestedMarkdownPattern.test(processed)) {
            console.log('Found nested markdown blocks, unwrapping them');
            processed = processed.replace(nestedMarkdownPattern, '$2');
        }
        
        // 1. Handle escaped newlines that should be actual newlines (common in JSON)
        processed = processed.replace(/\\n/g, '\n');
        
        // 2. Fix escaped quotes
        processed = processed.replace(/\\"/g, '"');
        
        // 3. Fix escaped backslashes
        processed = processed.replace(/\\\\/g, '\\');
        
        // 4. Fix improperly escaped code blocks
        processed = processed.replace(/\\`\\`\\`/g, '```');
        
        // 5. Fix markdown headings: Ensure a space after the # sequence
        // Improved regex to handle all heading levels correctly
        processed = processed.replace(/^(#{1,6})(?!\s|\#)(.+)$/gm, '$1 $2');
        
        // NEW: Special handling for financial notation with tildes to prevent markdown strikethrough
        // This replaces standalone tildes used in financial context (~$X.XX) with a special character
        // and then we'll handle it with CSS
        processed = processed.replace(/(\(?)~\$(\d+(\.\d+)?)/g, '$1<span class="approx-price">~</span>$$2');
        processed = processed.replace(/(\s)~\$(\d+(\.\d+)?)/g, '$1<span class="approx-price">~</span>$$2');
        
        // Also check for other financial notation patterns
        processed = processed.replace(/([^~])~(\d+(\.\d+)?%?)/g, '$1<span class="approx-price">~</span>$2');
        
        // NEW: Check and fix table formatting issues that cause horizontal scrolling
        // This detects markdown tables and adds special handling
        const hasMarkdownTables = /^\|.+\|$/m.test(processed);
        if (hasMarkdownTables) {
            console.log('Detected markdown tables, adding responsive table wrapper styling');
            // We'll handle this after parsing, by adding a CSS class
        }
        
        // 6. Fix HTML-like tags that might get stripped by DOMPurify
        // Replace them with markdown equivalents before the parsing happens
        processed = processed.replace(/<b>(.*?)<\/b>/g, '**$1**');
        processed = processed.replace(/<i>(.*?)<\/i>/g, '*$1*');
        processed = processed.replace(/<h([1-6])>(.*?)<\/h\1>/g, (match, level, content) => {
            return '#'.repeat(parseInt(level)) + ' ' + content;
        });
        
        console.log('Preprocessed markdown content:', 
            processed !== content ? 'Changes applied' : 'No changes needed');
        
        return processed;
    }
    
    function displayReport(report) {
        // Set title
        document.title = `LangAlpha | ${report.title || 'Investment Report'}`;
        
        // Display report metadata
        if (reportTitle) {
            reportTitle.textContent = report.title || 'Investment Report';
        }
        
        if (sessionIdDisplay && report.session_id) {
            sessionIdDisplay.textContent = report.session_id;
        } else if (sessionIdDisplay) {
            sessionIdDisplay.textContent = 'N/A';
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
            // DEBUG: Log raw content and parsed content to help diagnose rendering issues
            console.log('Raw report content:', report.content);
            
            // Diagnose potential markdown issues
            diagnoseMarkdownIssues(report.content);
            
            // Use the new renderReportContent function for better rendering
            renderReportContent(report);
        }
    }
    
    // New function to fix rendered content after it's added to the DOM
    function fixRenderedContent(contentElement) {
        // Fix tables to be responsive and not create horizontal scrolling
        const tables = contentElement.querySelectorAll('table');
        if (tables.length > 0) {
            console.log(`Found ${tables.length} tables, applying responsive styling`);
            
            tables.forEach((table, index) => {
                // Create a wrapper div with overflow handling
                const wrapper = document.createElement('div');
                wrapper.className = 'overflow-x-auto max-w-full my-4';
                
                // Move the table into the wrapper
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
                
                // Add styling to the table
                table.className = 'min-w-full table-auto border-collapse';
                
                // Add styling to table cells if needed
                const cells = table.querySelectorAll('th, td');
                cells.forEach(cell => {
                    cell.className = (cell.tagName === 'TH') 
                        ? 'px-4 py-2 bg-gray-100 dark:bg-gray-700 font-semibold border border-gray-200 dark:border-gray-600' 
                        : 'px-4 py-2 border border-gray-200 dark:border-gray-600';
                });
            });
        }
        
        // Fix code blocks to ensure they don't create horizontal scrolling
        const codeBlocks = contentElement.querySelectorAll('pre code');
        if (codeBlocks.length > 0) {
            console.log(`Found ${codeBlocks.length} code blocks, applying overflow handling`);
            
            codeBlocks.forEach(codeBlock => {
                const pre = codeBlock.parentNode;
                pre.className = 'overflow-x-auto max-w-full my-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-md';
            });
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

    function renderReportContent(report) {
        if (!report || !report.content) {
            console.log('Empty report or missing content');
            return;
        }
        
        console.log('Rendering report for session:', report.session_id);

        // Preprocess markdown content to fix common issues
        const preprocessedContent = preprocessMarkdown(report.content);
        
        try {
            // Use DOMPurify to sanitize, marked to render markdown
            const sanitizedHTML = marked.parse(preprocessedContent);
            const purified = DOMPurify.sanitize(sanitizedHTML);
            
            // Apply post-processing to fix any remaining issues
            const postProcessed = postprocessHTML(purified);
            
            document.getElementById('report-content').innerHTML = postProcessed;
            
            // Apply syntax highlighting to code blocks
            document.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
            
            // Apply responsive styling AFTER content is in the DOM
            fixRenderedContent(document.getElementById('report-content')); 
            
            console.log('Report content rendered successfully');
            
        } catch (error) {
            console.error('Error rendering markdown:', error);
            document.getElementById('report-content').textContent = report.content;
        }
    }
    
    function postprocessHTML(html) {
        if (!html) return html;
        
        let processed = html;
        
        // Fix specific rendering issues with financial notation
        // This ensures the tilde's special markup doesn't break
        const tildeSpanRegex = /<span class="approx-price">~<\/span>\$([\d\.]+)/g;
        if (tildeSpanRegex.test(processed)) {
            console.log('Found financial notation with special span, ensuring proper formatting');
        }
        
        // Fix any additional heading issues that weren't caught in preprocessing
        processed = processed.replace(/<h([1-6])>#+\s*(.*?)<\/h\1>/g, '<h$1>$2</h$1>');
        
        // Ensure tables have proper responsive behavior (handled by fixRenderedContent now)
        // processed = processed.replace(/<table>/g, '<div class="table-responsive"><table class="table">');
        // processed = processed.replace(/<\/table>/g, '</table></div>');
        
        // Ensure code blocks have proper syntax highlighting class if missing
        processed = processed.replace(/<pre><code>(?!<span)/g, '<pre><code class="hljs">');
        
        return processed;
    }
}); 