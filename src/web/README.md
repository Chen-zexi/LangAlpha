# Market Intelligence Agent Web API

This module provides a FastAPI-based web API for the Market Intelligence Agent workflow. It serves as the backend for web applications to interact with the agent system.

## File Structure

The `src/web` directory contains the following key files and directories:

-   `main.py`: The main FastAPI application file. Defines API endpoints, handles requests, and orchestrates the workflow streaming.
-   `run_server.py`: A simple script to run the FastAPI server using Uvicorn.
-   `static/`: Contains static assets for the web interface.
    -   `index.html`: The main interactive index page where users input queries and see the agent workflow.
    -   `report.html`: The page for displaying the final generated investment report.
    -   `history.html` (Optional): Page for viewing past sessions and reports.
    -   `session_history.html` (Optional): Page for viewing details of a specific session.
    -   (Other assets like CSS or JavaScript files might be placed here if needed).
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
    -   Provides "Back to Results", "Print", and "Download as PDF" (currently triggers print) actions.
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

Understanding these message types and their custom handling is essential when making UI changes or debugging the messaging flow. 