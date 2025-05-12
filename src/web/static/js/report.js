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
    const tradingViewWidgetsContainer = document.getElementById('tradingview-widgets-container');
    
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
                    }, 1000);
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
        const markdownCodeBlockPattern = /^```(markdown|md)?\\s+([\\s\\S]+?)\\s+```$/;
        const codeBlockMatch = processed.match(markdownCodeBlockPattern);
        
        if (codeBlockMatch) {
            console.log('Found entire content wrapped in markdown code block, unwrapping it');
            processed = codeBlockMatch[2] || codeBlockMatch[1];
        }
        
        // Also check for any nested markdown blocks
        const nestedMarkdownPattern = /```(markdown|md)\\s+([\\s\\S]+?)\\s+```/g;
        if (nestedMarkdownPattern.test(processed)) {
            console.log('Found nested markdown blocks, unwrapping them');
            processed = processed.replace(nestedMarkdownPattern, '$2');
        }
        
        // 1. Handle escaped newlines that should be actual newlines (common in JSON)
        processed = processed.replace(/\\\\n/g, '\\n');
        
        // 2. Fix escaped quotes
        processed = processed.replace(/\\\\"/g, '"');
        
        // 3. Fix escaped backslashes
        processed = processed.replace(/\\\\\\\\/g, '\\\\');
        
        // 4. Fix improperly escaped code blocks
        processed = processed.replace(/\\`\\`\\`/g, '```');
        
        // 5. Fix markdown headings: Ensure a space after the # sequence
        // Improved regex to handle all heading levels correctly
        processed = processed.replace(/^(#{1,6})(?!\s|#)(.+)$/gm, '$1 $2');
        
        // NEW: Unwrap generic code blocks that ONLY contain a markdown table
        // This runs after specific ```markdown block unwrapping.
        processed = processed.replace(/```\\s*([\\s\\S]*?)\\s*```/g, (match, contentInsideBlock) => {
            const contentTrimmed = contentInsideBlock.trim();
            if (!contentTrimmed) return match; // Empty block, leave as is

            const lines = contentTrimmed.split('\\n').map(l => l.trim());

            if (lines.length < 2) { // Needs at least header and separator
                return match;
            }

            // Check if all lines look like table rows (start and end with |)
            const allLinesAreTableRows = lines.every(line => line.startsWith('|') && line.endsWith('|'));
            
            if (!allLinesAreTableRows) {
                return match; // Block contains non-table-row lines, so it's not purely a table
            }

            // Check for a separator line: e.g., |---|---| or |:---|:--:|
            // Regex: Starts with |, then one or more groups of (optional space, optional colon, one or more hyphens, optional colon, optional space, |), ends line.
            const separatorLineRegex = /^\|(?:\s*:?-+:?\s*\|)+$/;
            const hasSeparatorLine = lines.some(line => separatorLineRegex.test(line));

            if (hasSeparatorLine) {
                // This block is very likely a markdown table wrapped in a generic code block.
                console.log('Found a markdown table wrapped in a generic code block, unwrapping it.');
                return contentTrimmed; // Return the unwrapped table content
            }

            return match; // Not a table by this definition, or contains other content; leave the code block.
        });
        
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
        processed = processed.replace(/<h([1-6])>(.*?)<\/h\1>/g, (match, level, hContent) => {
            return '#'.repeat(parseInt(level)) + ' ' + hContent;
        });
        
        console.log('Preprocessed markdown content:', 
            processed !== content ? 'Changes applied' : 'No changes needed');
        
        return processed;
    }
    
    // Initialize TradingView Symbol Info Widget
    function initTradingViewSymbolInfoWidget(symbol) {
        if (!symbol) {
            console.error('No symbol provided for TradingView widget');
            return;
        }
        
        console.log(`Initializing TradingView Symbol Info Widget for ${symbol}`);
        
        // Get the container element
        const container = document.getElementById('tradingview-symbol-info');
        if (!container) {
            console.error('TradingView widget container not found');
            return;
        }
        
        // Show the widgets container
        const widgetsContainer = document.getElementById('tradingview-widgets-container');
        if (widgetsContainer) {
            widgetsContainer.classList.remove('hidden');
        }
        
        // Add loading state
        container.classList.add('loading');
        
        try {
            // Detect dark mode using CSS media query
            const isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            const colorTheme = isDarkMode ? 'dark' : 'light';
            
            // Create the script element
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-info.js';
            script.async = true;
            
            // Set the widget configuration
            const widgetConfig = {
                symbol: symbol,
                width: "100%",
                locale: "en",
                colorTheme: colorTheme,
                isTransparent: true
            };
            
            console.log('TradingView widget config:', widgetConfig);
            script.innerHTML = JSON.stringify(widgetConfig);
            
            // Add event listener to remove loading state when script loads
            script.onload = function() {
                console.log('TradingView widget script loaded');
                setTimeout(() => {
                    container.classList.remove('loading');
                }, 10);
            };
            
            script.onerror = function(error) {
                console.error('Error loading TradingView widget script:', error);
                container.classList.remove('loading');
                showWidgetError(container, 'Failed to load widget');
            };
            
            // Add the script to the container
            const widgetDiv = container.querySelector('.tradingview-widget-container__widget');
            if (widgetDiv) {
                widgetDiv.innerHTML = ''; // Clear previous widget if any
                widgetDiv.appendChild(script);
            } else {
                console.error('Widget div not found in container');
                container.classList.remove('loading');
                showWidgetError(container, 'Widget container not found');
            }
        } catch (error) {
            console.error('Error initializing TradingView widget:', error);
            container.classList.remove('loading');
            showWidgetError(container, 'Error initializing widget');
        }
    }
    
    // Initialize TradingView Mini Chart Widget
    function initTradingViewMiniChartWidget(symbol) {
        if (!symbol) {
            console.error('No symbol provided for TradingView Mini Chart widget');
            return;
        }
        
        console.log(`Initializing TradingView Mini Chart Widget for ${symbol}`);
        
        // Get the container element
        const container = document.getElementById('tradingview-mini-chart');
        if (!container) {
            console.error('TradingView Mini Chart container not found');
            return;
        }
        
        // Add loading state
        container.classList.add('loading');
        
        try {
            // Detect dark mode using CSS media query
            const isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            const colorTheme = isDarkMode ? 'dark' : 'light';
            
            // Create the script element
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js';
            script.async = true;
            
            // Set the widget configuration
            const widgetConfig = {
                symbol: symbol,
                width: "100%",
                height: "100%",
                locale: "en",
                dateRange: "12M",
                colorTheme: colorTheme,
                isTransparent: true,
                autosize: true,
                largeChartUrl: "",
                chartOnly: true,
                noTimeScale: false
            };
            
            console.log('TradingView Mini Chart widget config:', widgetConfig);
            script.innerHTML = JSON.stringify(widgetConfig);
            
            // Add event listener to remove loading state when script loads
            script.onload = function() {
                console.log('TradingView Mini Chart widget script loaded');
                setTimeout(() => {
                    container.classList.remove('loading');
                }, 0);
            };
            
            script.onerror = function(error) {
                console.error('Error loading TradingView Mini Chart widget script:', error);
                container.classList.remove('loading');
                showWidgetError(container, 'Failed to load chart widget');
            };
            
            // Add the script to the container
            const widgetDiv = container.querySelector('.tradingview-widget-container__widget');
            if (widgetDiv) {
                widgetDiv.innerHTML = ''; // Clear previous widget if any
                widgetDiv.appendChild(script);
            } else {
                console.error('Widget div not found in container');
                container.classList.remove('loading');
                showWidgetError(container, 'Chart widget container not found');
            }
        } catch (error) {
            console.error('Error initializing TradingView Mini Chart widget:', error);
            container.classList.remove('loading');
            showWidgetError(container, 'Error initializing chart widget');
        }
    }
    
    // Initialize TradingView Market Overview Widget
    function initTradingViewMarketOverviewWidget() {
        console.log(`Initializing TradingView Market Overview Widget`);
        
        // Get the container element
        const container = document.getElementById('tradingview-market-overview');
        if (!container) {
            console.error('TradingView Market Overview widget container not found');
            return;
        }
        
        // Add loading state
        container.classList.add('loading');
        
        try {
            // Detect dark mode using CSS media query
            const isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            const colorTheme = isDarkMode ? 'dark' : 'light';
            
            // Create the script element
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
            script.async = true;
            
            // Set the widget configuration with predefined market symbols
            const widgetConfig = {
                "symbols": [
                    ["SPREADEX:SPX|1D"],
                    ["NASDAQ:NDX|1D"],
                    ["PYTH:US10Y|1D"],
                    ["EIGHTCAP:VIX|1D"],
                    ["TVC:GOLD|1D"]
                ],
                "chartOnly": false,
                "width": "100%",
                "height": "100%",
                "locale": "en",
                "colorTheme": colorTheme,
                "autosize": true,
                "showVolume": true,
                "showMA": false,
                "hideDateRanges": false,
                "hideMarketStatus": false,
                "hideSymbolLogo": false,
                "scalePosition": "right",
                "isTransparent": true,
                "scaleMode": "Normal",
                "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
                "fontSize": "10",
                "noTimeScale": false,
                "valuesTracking": "1",
                "changeMode": "price-and-percent",
                "chartType": "area",
                "maLineColor": "#2962FF",
                "maLineWidth": 1,
                "maLength": 9,
                "headerFontSize": "small",
                "lineWidth": 2,
                "lineType": 0,
                "dateRanges": [
                    "1d|1",
                    "1m|30",
                    "3m|60",
                    "12m|1D",
                    "60m|1W",
                    "all|1M"
                ]
            };
            
            console.log('TradingView Market Overview widget config:', widgetConfig);
            script.innerHTML = JSON.stringify(widgetConfig);
            
            // Add event listener to remove loading state when script loads
            script.onload = function() {
                console.log('TradingView Market Overview widget script loaded');
                setTimeout(() => {
                    container.classList.remove('loading');
                }, 0);
            };
            
            script.onerror = function(error) {
                console.error('Error loading TradingView Market Overview widget script:', error);
                container.classList.remove('loading');
                showWidgetError(container, 'Failed to load market overview widget');
            };
            
            // Add the script to the container
            const widgetDiv = container.querySelector('.tradingview-widget-container__widget');
            if (widgetDiv) {
                widgetDiv.innerHTML = ''; // Clear previous widget if any
                widgetDiv.appendChild(script);
            } else {
                console.error('Widget div not found in container');
                container.classList.remove('loading');
                showWidgetError(container, 'Market overview widget container not found');
            }
        } catch (error) {
            console.error('Error initializing TradingView Market Overview widget:', error);
            container.classList.remove('loading');
            showWidgetError(container, 'Error initializing market overview widget');
        }
    }
    
    // Helper function to show widget errors
    function showWidgetError(container, message) {
        // Create an error message element
        const errorDiv = document.createElement('div');
        errorDiv.className = 'bg-red-100 text-red-700 p-4 rounded-lg text-center';
        errorDiv.innerHTML = `
            <p class="font-medium">Widget Error</p>
            <p class="text-sm">${message}</p>
        `;
        
        // Clear the container and add the error message
        if (container) {
            const widgetDiv = container.querySelector('.tradingview-widget-container__widget');
            if (widgetDiv) {
                widgetDiv.innerHTML = '';
                widgetDiv.appendChild(errorDiv);
            } else {
                container.innerHTML = '';
                container.appendChild(errorDiv);
            }
        }
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
        
        // Check for ticker info in report metadata
        if (report.metadata && report.metadata.tickers && report.metadata.tickers.length > 0) {
            console.log('Ticker info found in report metadata:', report.metadata.tickers);
            
            // Get the ticker type from metadata or default to market if not provided
            const tickerType = report.metadata.ticker_type ? report.metadata.ticker_type.toLowerCase() : 'market';
            console.log('Ticker type:', tickerType);
            
            // Show appropriate widget based on ticker type
            showTradingViewWidget(tickerType, report.metadata.tickers);
        } else {
            console.log('No ticker info found in report metadata - defaulting to market view');
            
            // Show market widget by default even when no tickers are available
            showTradingViewWidget('market', []);
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
    
    // Function to display appropriate TradingView widget based on ticker type
    function showTradingViewWidget(tickerType, tickerInfoList) {
        // Show the main widgets container
        if (tradingViewWidgetsContainer) {
            tradingViewWidgetsContainer.classList.remove('hidden');
        } else {
            console.error('TradingView widgets container not found');
            return;
        }
        
        // Hide all widget types first
        document.getElementById('tradingview-symbol-widget').classList.add('hidden');
        document.getElementById('tradingview-market-widget').classList.add('hidden');
        document.getElementById('tradingview-multiple-widget').classList.add('hidden');
        document.getElementById('tradingview-compare-widget').classList.add('hidden');
        
        console.log(`Showing widget for ticker type: ${tickerType} with ${tickerInfoList.length} tickers`);
        
        // Show appropriate widget based on ticker type
        if (tickerType === 'company' || tickerType === 'etf') {
            // Company or ETF - Show Symbol Info + Mini Chart
            const symbolWidget = document.getElementById('tradingview-symbol-widget');
            if (symbolWidget) {
                symbolWidget.classList.remove('hidden');
                
                // Get the first ticker
                const firstTicker = tickerInfoList[0];
                
                // Format ticker for TradingView
                const tickerSymbol = formatTickerForTradingView(firstTicker);
                
                if (tickerSymbol) {
                    // Initialize TradingView widgets with the ticker symbol
                    initTradingViewSymbolInfoWidget(tickerSymbol);
                    initTradingViewMiniChartWidget(tickerSymbol);
                    console.log(`Initialized symbol widgets for ${tickerSymbol}`);
                } else {
                    console.warn('Could not format ticker symbol from:', firstTicker);
                    symbolWidget.classList.add('hidden');
                    tradingViewWidgetsContainer.classList.add('hidden');
                }
            }
        } else if (tickerType === 'market') {
            // Market - Show Market Overview (with predefined symbols, no need for tickers)
            const marketWidget = document.getElementById('tradingview-market-widget');
            if (marketWidget) {
                marketWidget.classList.remove('hidden');
                
                // Initialize the market overview widget with predefined symbols
                // This will work even if tickerInfoList is empty
                initTradingViewMarketOverviewWidget();
                console.log('Initialized market overview widget');
            }
        } else if (tickerType === 'multiple') {
            // Multiple tickers - Show Multiple Symbols widget
            const multipleWidget = document.getElementById('tradingview-multiple-widget');
            if (multipleWidget) {
                multipleWidget.classList.remove('hidden');
                
                // Make sure we have at least one ticker
                if (tickerInfoList.length > 0) {
                    // Get formatted ticker symbols
                    const formattedTickers = tickerInfoList.map(ticker => formatTickerForTradingView(ticker)).filter(Boolean);
                    
                    if (formattedTickers.length > 0) {
                        // Initialize widget for multiple ticker symbols
                        initTradingViewMultipleSymbolsWidget(formattedTickers);
                        console.log(`Initialized multiple symbols widget with ${formattedTickers.length} tickers`);
                    } else {
                        console.warn('Could not format any tickers for multiple widget');
                        multipleWidget.classList.add('hidden');
                        tradingViewWidgetsContainer.classList.add('hidden');
                    }
                } else {
                    console.warn('No tickers available for multiple widget');
                    multipleWidget.classList.add('hidden');
                    tradingViewWidgetsContainer.classList.add('hidden');
                }
            }
        } else if (tickerType === 'compare') {
            // Compare - Show Compare Symbols widget
            const compareWidget = document.getElementById('tradingview-compare-widget');
            if (compareWidget) {
                compareWidget.classList.remove('hidden');
                
                // Make sure we have at least two tickers
                if (tickerInfoList.length >= 2) {
                    // Format tickers for TradingView
                    const mainSymbol = formatTickerForTradingView(tickerInfoList[0]);
                    const compareSymbol = formatTickerForTradingView(tickerInfoList[1]);
                    
                    if (mainSymbol && compareSymbol) {
                        // Initialize compare symbols widget
                        initTradingViewCompareSymbolsWidget(mainSymbol, compareSymbol);
                        console.log(`Initialized compare symbols widget for ${mainSymbol} and ${compareSymbol}`);
                    } else {
                        console.warn('Could not format ticker symbols for comparison');
                        compareWidget.classList.add('hidden');
                        tradingViewWidgetsContainer.classList.add('hidden');
                    }
                } else {
                    console.warn('Need at least two tickers for compare widget');
                    compareWidget.classList.add('hidden');
                    tradingViewWidgetsContainer.classList.add('hidden');
                }
            }
        } else {
            console.warn('Unknown ticker type:', tickerType);
            tradingViewWidgetsContainer.classList.add('hidden');
        }
    }
    
    // Helper function to format ticker symbols for TradingView
    function formatTickerForTradingView(ticker) {
        if (!ticker) return null;
        
        // If ticker object has tradingview_symbol property, use it directly
        if (typeof ticker === 'object') {
            if (ticker.tradingview_symbol) {
                return ticker.tradingview_symbol;
            }
            
            // If no tradingview_symbol but we have exchange and ticker, construct it
            if (ticker.exchange && ticker.ticker) {
                return `${ticker.exchange}:${ticker.ticker}`;
            }
            
            // If we just have a ticker property, use it with default exchange
            if (ticker.ticker) {
                return `NASDAQ:${ticker.ticker}`;
            }
            
            // If we have a symbol property (sometimes used instead of ticker)
            if (ticker.symbol) {
                // Check if symbol already contains exchange prefix
                if (ticker.symbol.includes(':')) {
                    return ticker.symbol;
                }
                return `NASDAQ:${ticker.symbol}`;
            }
        }
        
        // If ticker is a string, handle it as before
        if (typeof ticker === 'string') {
            // If ticker already includes an exchange prefix like 'NASDAQ:AAPL', use it directly
            if (ticker.includes(':')) {
                return ticker;
            }
            
            // For US stocks, default to NASDAQ if no exchange is specified
            return `NASDAQ:${ticker}`;
        }
        
        // Return null if we couldn't determine a valid format
        console.error('Unable to format ticker for TradingView:', ticker);
        return null;
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
        
        const errorTextElement = document.getElementById('error-message-text');
        if (errorTextElement) {
            errorTextElement.textContent = message;
        } else {
            // Fallback if span doesn't exist
            errorMessage.innerHTML = `<div class="flex items-center"><i class="fa-solid fa-triangle-exclamation mr-3 text-xl"></i>${message}</div>`;
        }
        
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
        
        
        return processed;
    }

    // Initialize TradingView Multiple Symbols Widget
    function initTradingViewMultipleSymbolsWidget(tickers) {
        if (!tickers || !Array.isArray(tickers) || tickers.length === 0) {
            console.error('No valid tickers provided for Multiple Symbols widget');
            return;
        }
        
        console.log(`Initializing TradingView Multiple Symbols Widget for ${tickers.length} tickers`);
        
        // Get the container element
        const container = document.getElementById('tradingview-multiple-symbols');
        if (!container) {
            console.error('TradingView Multiple Symbols container not found');
            return;
        }
        
        // Add loading state
        container.classList.add('loading');
        
        try {
            // Detect dark mode using CSS media query
            const isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            const colorTheme = isDarkMode ? 'dark' : 'light';
            
            // Format tickers for TradingView symbols array
            const formattedSymbols = tickers.slice(0, 5).map(ticker => {
                const symbol = formatTickerForTradingView(ticker);
                // Format each symbol for the widget
                if (symbol) {
                    if (symbol.includes('|')) {
                        return [symbol];
                    } else {
                        return [`${symbol}|1D`];
                    }
                }
                return null;
            }).filter(Boolean); // Remove any null values
            
            if (formattedSymbols.length === 0) {
                console.error('No valid formatted symbols for Multiple Symbols widget');
                container.classList.remove('loading');
                showWidgetError(container, 'No valid symbols to display');
                return;
            }
            
            // Create the script element
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
            script.async = true;
            
            // Set the widget configuration
            const widgetConfig = {
                "symbols": formattedSymbols,
                "chartOnly": false,
                "width": "100%",
                "height": "100%",
                "locale": "en",
                "colorTheme": colorTheme,
                "autosize": true,
                "showVolume": true,
                "showMA": false,
                "hideDateRanges": false,
                "hideMarketStatus": false,
                "hideSymbolLogo": false,
                "scalePosition": "right",
                "scaleMode": "Normal",
                "isTransparent": true,
                "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
                "fontSize": "10",
                "noTimeScale": false,
                "valuesTracking": "1",
                "changeMode": "price-and-percent",
                "chartType": "area",
                "maLineColor": "#2962FF",
                "maLineWidth": 1,
                "maLength": 9,
                "headerFontSize": "small",
                "lineWidth": 2,
                "lineType": 0,
                "dateRanges": [
                    "1d|1",
                    "1m|30",
                    "3m|60",
                    "12m|1D",
                    "60m|1W",
                    "all|1M"
                ]
            };
            
            console.log('TradingView Multiple Symbols widget config:', widgetConfig);
            script.innerHTML = JSON.stringify(widgetConfig);
            
            // Add event listener to remove loading state when script loads
            script.onload = function() {
                console.log('TradingView Multiple Symbols widget script loaded');
                setTimeout(() => {
                    container.classList.remove('loading');
                }, 0);
            };
            
            script.onerror = function(error) {
                console.error('Error loading TradingView Multiple Symbols widget script:', error);
                container.classList.remove('loading');
                showWidgetError(container, 'Failed to load multiple symbols widget');
            };
            
            // Add the script to the container
            const widgetDiv = container.querySelector('.tradingview-widget-container__widget');
            if (widgetDiv) {
                widgetDiv.innerHTML = ''; // Clear previous widget if any
                widgetDiv.appendChild(script);
            } else {
                console.error('Widget div not found in container');
                container.classList.remove('loading');
                showWidgetError(container, 'Multiple symbols widget container not found');
            }
        } catch (error) {
            console.error('Error initializing TradingView Multiple Symbols widget:', error);
            container.classList.remove('loading');
            showWidgetError(container, 'Error initializing multiple symbols widget');
        }
    }
    
    // Initialize TradingView Compare Symbols Widget
    function initTradingViewCompareSymbolsWidget(mainSymbol, compareSymbol) {
        console.log(`Initializing TradingView Compare Symbols Widget: ${mainSymbol} vs ${compareSymbol}`);
        
        // Get the container element
        const container = document.getElementById('tradingview-symbol-compare');
        if (!container) {
            console.error('TradingView Compare Symbols container not found');
            return;
        }
        
        // Add loading state
        container.classList.add('loading');
        
        try {
            // Detect dark mode using CSS media query
            const isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            const colorTheme = isDarkMode ? 'dark' : 'light';
            
            // Extract symbol name for display if possible
            let mainName = "Main Symbol";
            if (mainSymbol.includes(':')) {
                const parts = mainSymbol.split(':');
                if (parts.length > 1) {
                    mainName = parts[1];
                }
            }
            
            // Format the main symbol if it's not in the right format
            let formattedMainSymbol = mainSymbol;
            if (!mainSymbol.includes('|')) {
                formattedMainSymbol = `${mainSymbol}|12M`;
            }
            
            // Format the compare symbol for the compareSymbol object
            let formattedCompareSymbol = compareSymbol;
            if (!compareSymbol.includes('|')) {
                formattedCompareSymbol = compareSymbol;
            }
            
            // Create the script element
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
            script.async = true;
            
            // Set the widget configuration
            const widgetConfig = {
                "symbols": [
                    [
                        mainName,
                        formattedMainSymbol
                    ],
                    [
                        formattedCompareSymbol
                    ]
                ],
                "chartOnly": false,
                "width": "100%",
                "height": "100%",
                "locale": "en",
                "colorTheme": colorTheme,
                "autosize": true,
                "showVolume": true,
                "showMA": false,
                "hideDateRanges": false,
                "hideMarketStatus": false,
                "hideSymbolLogo": false,
                "scalePosition": "right",
                "scaleMode": "Percentage",
                "isTransparent": true,
                "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
                "fontSize": "10",
                "noTimeScale": false,
                "valuesTracking": "1",
                "changeMode": "price-and-percent",
                "chartType": "area",
                "maLineColor": "#2962FF",
                "maLineWidth": 1,
                "maLength": 9,
                "headerFontSize": "small",
                "lineWidth": 2,
                "lineType": 0,
                "compareSymbol": {
                    "symbol": compareSymbol,
                    "lineColor": "#FF9800",
                    "lineWidth": 2,
                    "showLabels": true
                },
                "dateRanges": [
                    "1d|1",
                    "1m|30",
                    "3m|60",
                    "12m|1D",
                    "60m|1W",
                    "all|1M"
                ]
            };
            
            console.log('TradingView Compare Symbols widget config:', widgetConfig);
            script.innerHTML = JSON.stringify(widgetConfig);
            
            // Add event listener to remove loading state when script loads
            script.onload = function() {
                console.log('TradingView Compare Symbols widget script loaded');
                setTimeout(() => {
                    container.classList.remove('loading');
                }, 0);
            };
            
            script.onerror = function(error) {
                console.error('Error loading TradingView Compare Symbols widget script:', error);
                container.classList.remove('loading');
                showWidgetError(container, 'Failed to load compare symbols widget');
            };
            
            // Add the script to the container
            const widgetDiv = container.querySelector('.tradingview-widget-container__widget');
            if (widgetDiv) {
                widgetDiv.innerHTML = ''; // Clear previous widget if any
                widgetDiv.appendChild(script);
            } else {
                console.error('Widget div not found in container');
                container.classList.remove('loading');
                showWidgetError(container, 'Compare symbols widget container not found');
            }
        } catch (error) {
            console.error('Error initializing TradingView Compare Symbols widget:', error);
            container.classList.remove('loading');
            showWidgetError(container, 'Error initializing compare symbols widget');
        }
    }
}); 