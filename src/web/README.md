# Market Intelligence Agent Web API

This module provides a FastAPI-based web API for the Market Intelligence Agent workflow. It serves as the backend for web applications to interact with the agent system.

## File Structure

The `src/web` directory contains the following key files and directories:

-   `main.py`: The main FastAPI application file. Defines API endpoints, handles requests, and orchestrates the workflow streaming.
-   `run_server.py`: A simple script to run the FastAPI server using Uvicorn.
-   `static/`: Contains static assets for the web interface.
    -   `css/`: Contains stylesheets for the web app
       -   `index.css`: Defines UI styles, agent colors, and animations for the main app
    -   `js/`: Contains JavaScript files that handle client-side functionality
       -   `index.js`: Handles the main workflow UI, SSE connections, and dynamic rendering
       -   `report.js`: Manages report display, PDF generation, and navigation
    -   `index.html`: The main interactive index page where users input queries and see the agent workflow.
    -   `report.html`: The page for displaying the final generated investment report.
    -   `history.html` (Optional): Page for viewing past sessions and reports.
    -   `session_history.html` (Optional): Page for viewing details of a specific session.
-   `templates/`: Contains HTML templates used by the API endpoints.
-   `requirements.txt`: Lists Python dependencies required for the web API.
-   `Dockerfile`: Defines the Docker image build process for the web service.
-   `README.md`: This documentation file.

## Setup

### Option 1: Running with Docker (Recommended)

1.  Make sure you have Docker and Docker Compose installed.
2.  From the project root directory, run: `docker-compose up -d`
3.  This starts all services, including the Web API at `http://localhost:8000`.

### Option 2: Running Locally

1.  Install dependencies: `cd src/web && pip install -r requirements.txt`
2.  Ensure the LangGraph API service is running (e.g., via `docker-compose up -d langgraph-api langgraph-redis langgraph-postgres`).
3.  Set environment variables (especially `LANGGRAPH_API_URL`, `MONGODB_URI`, `MONGODB_DB_NAME`). See `.env.example` in the project root.
4.  Run the server from the project root: `python -m src.web.run_server`
5.  The API server will start at `http://localhost:8000`.

## API Endpoints

The FastAPI application (`main.py`) provides the following endpoints:

### Workflow Execution

-   **POST `/api/run-workflow`**:
    -   Initiates the market intelligence workflow based on the provided query.
    -   **Request Body**: `{ "request": { "query": "Your query here" }, "config": { ...optional config... } }`
    -   **Response**: Returns a 200 OK status with a `Content-Location` header pointing to the streaming endpoint (e.g., `/api/run-workflow/stream/{run_id}`).
-   **GET `/api/run-workflow/stream/{run_id}`**:
    -   Streams the workflow results using Server-Sent Events (SSE).
    -   Clients connect to this endpoint using the `run_id` obtained from the POST request.
    -   Streams JSON objects containing agent logs, state transitions, and the final report.

### Report and History Management (MongoDB)

-   **POST `/api/create-report`**:
    -   Endpoint called by the frontend (`index.html`) when the reporter agent finishes, ensuring the report is saved to MongoDB even if not explicitly sent in the stream.
    -   **Request Body**: `{ "content": "Report markdown", "title": "Report title", "metadata": { "query": "Original query" } }`
    -   **Response**: `{ "success": true, "report_id": "mongo_db_object_id" }`
-   **GET `/api/recent-reports`**:
    -   Fetches a list of the most recent reports stored in MongoDB.
    -   Used by `index.html` to populate the "Recent Searches" sidebar.
    -   **Query Parameter**: `limit` (optional, default 5)
    -   **Response**: `{ "reports": [ { "_id": "...", "title": "...", "timestamp": "...", "metadata": {...} }, ... ] }`
-   **GET `/api/history/report/{report_id}`**:
    -   Fetches the details of a specific report by its MongoDB `_id`.
    -   Used by `report.html` to display the report content.
    -   **Response**: The report document from MongoDB (JSON).
-   **(Other History Endpoints)**: `/api/history/sessions`, `/api/history/messages/{session_id}`, `/api/history/reports/{session_id}` are defined for potential future history browsing features.

### Utility

-   **GET `/api/health`**: Standard health check endpoint.
-   **GET `/`**, **GET `/index`**: Redirect to the main index page (`static/index.html`).
-   **GET `/report`**: Renders the report page (`static/report.html`), optionally taking a `report_id` query parameter.

## MongoDB Integration

The web API integrates with MongoDB to store and retrieve workflow history and generated reports.

-   **Database Models**: Defined in `src/database/models/`:
    -   `messages.py`: Defines the structure for storing individual messages (user queries, agent outputs, system events) associated with a session.
    -   `reports.py`: Defines the structure for storing the final generated reports, including content, title, timestamp, and metadata (like the original query).
-   **Database Utils**: `src/database/utils/mongo_client.py` handles the connection to the MongoDB instance using environment variables (`MONGODB_URI`, `MONGODB_DB_NAME`).
-   **Data Stored**:
    -   **Reports Collection**: Stores the final `Report` objects generated by the workflow. Each report includes a `session_id`, `timestamp`, `title`, markdown `content`, and `metadata` (containing the original user `query`).
    -   **Messages Collection**: Stores `Message` objects representing the flow of communication within a workflow session (user input, agent steps, system messages). Each message is linked by `session_id`.

## Frontend Logic (`index.html` and `report.html`)

-   **`index.html`**:
    -   Handles user query input and initiates the workflow via `/api/run-workflow`.
    -   Connects to the SSE stream endpoint provided in the response header.
    -   Parses incoming SSE messages and dynamically renders the agent workflow steps using JavaScript (`appendLogMessage`, `formatChunkForRendering`).
    -   Handles different message types (status, agent output, plan steps, errors) with specific UI elements and styling.
    -   Manages UI state (e.g., processing indicators, button states).
    -   Fetches and displays recent reports from `/api/recent-reports` in the sidebar.
    -   Handles navigation to the `report.html` page when the "View Complete Investment Report" button is clicked, passing the `report_id`.
    -   Uses `localStorage` temporarily to cache the workflow state (HTML content, scroll position) when navigating *to* the report page, allowing seamless return using the "Back to Results" button on the report page.
-   **`report.html`**:
    -   Retrieves the `report_id` from the URL query parameters.
    -   Fetches the corresponding report data from MongoDB via the `/api/history/report/{report_id}` endpoint.
    -   Renders the report title, query, timestamp, and markdown content using `marked.js` and `DOMPurify`.
    -   Provides "Back to Results", "Print", and "Download as PDF" (implemented with html2pdf.js library).
    -   The "Back to Results" button navigates back to `index.html`, triggering the restoration of the cached workflow state from `localStorage`.

## Data Flow Summary

1.  **User Query**: User enters a query in `index.html`.
2.  **Workflow Initiation**: Frontend sends POST request to `/api/run-workflow`.
3.  **Streaming**: Backend initiates LangGraph workflow, gets a `run_id`, and returns the stream URL (`/api/run-workflow/stream/{run_id}`) in the `Content-Location` header.
4.  **SSE Connection**: Frontend connects to the stream URL via EventSource.
5.  **Agent Processing**: Backend streams workflow updates (agent steps, status changes) as JSON objects via SSE. Messages and events are saved to the `messages` collection in MongoDB.
6.  **Frontend Rendering**: `index.html` receives SSE messages and renders the workflow progress dynamically.
7.  **Report Generation & Saving**: When the reporter agent finishes:
    -   Frontend (`index.html`) sends a POST request to `/api/create-report` with the generated report content.
    -   Backend saves the report to the `reports` collection in MongoDB and returns the `report_id`.
    -   Frontend stores this `report_id` (`window.currentReportId`).
8.  **View Report**: User clicks "View Complete Investment Report" in `index.html`.
    -   Frontend saves its current state (HTML, scroll position) to `localStorage`.
    -   Frontend navigates to `report.html?report_id={report_id}`.
9.  **Report Display**: `report.html` fetches the report data from `/api/history/report/{report_id}` using the ID from the URL and renders it.
10. **Return to Workflow**: User clicks "Back to Results" in `report.html`.
    -   Navigates back to `index.html`.
    -   `index.html` detects the return trip (via `localStorage` flag), restores its previous HTML content and scroll position from `localStorage`, bypassing the "Recent Reports" load.
11. **Recent Reports**: `index.html` sidebar fetches recent reports from `/api/recent-reports` on initial load (if not returning from `report.html`). Clicking a report link navigates directly to `report.html?report_id={report_id}`.

## UI Components and Styling

### Agent Color Scheme and Icons

Each agent has a dedicated color and styling defined in `static/css/index.css`:

- **Planner**: Light green (#C7F572), iconography uses "P"
- **Supervisor**: Medium green (#A4CA7A), iconography uses "S"
- **Researcher**: Darker green (#95C98D), iconography uses "R"
- **Market**: Blue (#30B0C7), iconography uses "M"
- **Coder**: Mint green (#8FD396), iconography uses "C"
- **Browser**: Pink (#F28AB5), iconography uses "B"
- **Analyst**: Yellow (#FFD60A), iconography uses "A"
- **Reporter**: Purple (#AF8CFF), iconography uses "R"

These colors are used consistently for agent icons, borders, and highlights throughout the UI.

### Important UI Components

1. **Status Indicator**:
   - Located in the header of the results container
   - Updates to show the current state of the workflow (Ready, Processing, Success, Error)
   - Changes color based on status (gray, blue, green, red)

2. **Agent Message Cards**:
   - Styled with agent-specific left borders and icons
   - Display agent outputs with markdown formatting
   - Handle different content types appropriately (text, code, tables)

3. **Plan Steps Component**:
   - Expandable/collapsible container for planner's steps
   - Shows chevron icon that rotates when expanded/collapsed
   - Displays individual steps with agent icons and task details

4. **Loading Indicators**:
   - Uses animated typing dots for in-progress states
   - Different animations for different loading states
   - Agent-specific loading states with appropriate messaging

5. **Example Queries**:
   - Shown in the empty state of the results container
   - Quick-start options for demonstrating the system
   - Clickable buttons that populate the query input

## Maintenance Tips

### Adding New Agents

If you need to add a new agent to the workflow:

1. Add the agent's color to the theme in `index.html`:
   ```javascript
   agent: {
     newagent: '#HEX_COLOR',
   }
   ```

2. Add corresponding CSS classes in `index.css`:
   ```css
   .agent-icon-newagent { background-color: #HEX_COLOR; color: white; }
   .border-agent-newagent { border-color: #HEX_COLOR; }
   ```

3. Update the message handling in `main.py` to process outputs from the new agent.

4. Add any special UI handling in `index.js` if the agent requires unique display logic.

### Modifying the Plan Steps UI

The Plan Steps component has a specific structure:

1. The handoff message appears before the expandable component.
2. The expandable header contains "Plan Steps" text and a chevron icon.
3. The chevron rotates to indicate expansion/collapse state.
4. Individual plan steps are rendered inside with their own styling.

If modifying this component:
- Maintain the parent-child relationship between containers
- Preserve the chevron rotation behavior
- Keep consistent with the agent color scheme

### Debugging SSE Connections

If you encounter issues with the streaming connection:

1. Check browser console for EventSource errors
2. Verify the API is returning the correct `Content-Location` header
3. Look for any CORS issues if accessing from different domains
4. Check if the stream is timing out (default timeout may need adjustment)
5. Use the logging in `main.py` to trace message flow

### Common UI Issues and Solutions

1. **Loading Indicators Not Disappearing**:
   - The code includes `hideAgentProcessing()` to remove old loading indicators
   - Ensure this function is called when agents complete their work

2. **Duplicate Messages**:
   - The backend may send the same content in multiple message types
   - Use conditional checks like: `if (log.type === 'status' && log.content === 'specific message') return;`

3. **Markdown Rendering Issues**:
   - The app uses marked.js with specific configuration
   - Content is sanitized with DOMPurify before insertion
   - Check both libraries' configuration if rendering problems occur

4. **PDF Generation Problems**:
   - PDF generation uses html2pdf.js
   - Ensure the content container has properly rendered before generating
   - Consider alternative libraries like jsPDF if needed

## Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## index Interface

The main index interface is available at `http://localhost:8000/` or `http://localhost:8000/static/index.html`.

## Environment Variables

Key environment variables (set in `.env` file or system environment):

-   `LANGGRAPH_API_URL`: URL of the LangGraph API service (default: `http://localhost:8123`).
-   `MONGODB_URI`: Connection string for your MongoDB instance.
-   `MONGODB_DB_NAME`: Name of the database to use in MongoDB.
-   `PORT`: Port for the web API server (default: 8000).
-   `HOST`: Host for the web API server (default: 0.0.0.0).
-   `LOG_LEVEL`: Logging level (default: info).

## Message Types and Frontend Handling

The streaming API uses a structured message format to communicate agent activities and outputs. The frontend handles different message types with specific display logic:

### Message Types

1. **Control Messages**: 
   - `connection_established` - Initial connection confirmation
   - `stream_complete` - Stream has ended
   - These are logged but not displayed to the user

2. **Status Messages**: 
   - `type: "status"` - Indicates an agent's processing state
   - Example: "Researcher is gathering information..."
   - Displayed as in-progress indicators with animated dots
   - When a new agent takes over, previous status messages may be hidden

3. **Agent Output Messages**:
   - `type: "agent_output"` - Contains completed work from an agent
   - Agent-specific formatting:
     - **Planner**: Shows title and thought process, with expandable plan steps
     - **Researcher/Market/Coder**: Shows a summary of findings/results
     - **Analyst**: Shows a standardized message "Analyst has finished generating insight"
     - **Reporter**: Shows confirmation of task completion before final report

4. **Plan Step Messages**:
   - `type: "plan_step"` - Contains details about steps in the planner's plan
   - Displayed in an expandable container under the planner's output

5. **Separator Messages**:
   - `type: "separator"` - Visual dividers between message sections
   - Rendered as horizontal rules of varying thickness

6. **Final Report Messages**:
   - `type: "final_report"` - The complete analysis compiled by the reporter agent
   - Displayed in a highlighted box with markdown formatting
   - Triggers UI state changes (success indicators, view report buttons)

7. **Error Messages**:
   - `type: "error"` - Indicates an error in processing
   - Displayed prominently with red styling

### Special Agent Handling

- **Planner**: Plan steps are grouped and made expandable/collapsible
- **Supervisor**: Messages shown inline as status updates, not as agent cards
- **Analyst**: Original detailed output is replaced with a standardized message
- **Reporter**: Final output includes styling for the full investment report

## Key JavaScript Components and Functions

### In `index.js`

1. **SSE Connection Management**:
   - `submitBtn.addEventListener('click', async () => {...})` - Initiates the workflow
   - `eventSource = new EventSource(sseUrl)` - Establishes the streaming connection
   - `eventSource.onmessage = (event) => {...}` - Handles incoming stream messages

2. **Message Rendering**:
   - `appendLogMessage(log)` - Core function for rendering different message types
   - `createPlanStepElement(log)` - Helper for formatting individual plan steps
   - `displayContent(element, markdown)` - Renders markdown content securely

3. **UI State Management**:
   - `updateStatus(message, status)` - Updates the status indicator
   - `hideAgentProcessing(agentName)` - Removes loading indicators when agents complete
   - `hideAllStatusMessages()` - Cleans up when report is ready

4. **Navigation & Storage**:
   - `savePageStateAndNavigateToReport()` - Caches state and navigates to report view
   - `checkReturnFromReport()` - Restores state when returning from report view
   - `reattachEventListeners()` - Ensures interactive elements work after state restoration

### In `report.js`

1. **Report Loading**:
   - `loadReport(id)` - Fetches report data from the API
   - `displayReport(report)` - Renders the report content

2. **PDF Generation**:
   - `downloadButton.addEventListener('click', () => {...})` - Handles PDF creation
   - Uses html2pdf.js to convert report content to downloadable PDF

Understanding these components and their interactions is essential when making UI changes or debugging message flow. 