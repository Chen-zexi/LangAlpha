# Market Intelligence Agent Web API

This module provides a FastAPI-based web API for the Market Intelligence Agent workflow. It serves as the backend for web applications to interact with the agent system.

## Setup

### Option 1: Running with Docker (Recommended)

1. Make sure you have Docker and Docker Compose installed.

2. From the project root directory, run:

```bash
docker-compose up -d
```

This will start all services including:
- LangGraph Redis service
- LangGraph PostgreSQL database
- LangGraph API service
- Web API service

The Web API will be available at http://localhost:8000.

### Option 2: Running Locally

1. Install the required dependencies:

```bash
cd src/web
pip install -r requirements.txt
```

2. Make sure the LangGraph API service is running (defined in `docker-compose.yml`):

```bash
docker-compose up -d langgraph-redis langgraph-postgres langgraph-api
```

3. Set the environment variable for the LangGraph API URL (default is http://localhost:8123):

```bash
export LANGGRAPH_API_URL=http://localhost:8123
```

4. Run the FastAPI server:

```bash
# From project root directory
python -m src.web.run_server
```

The API server will start at http://localhost:8000.

## API Endpoints

### Run Workflow

- **URL**: `/api/run-workflow`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "query": "Your market intelligence question here"
  }
  ```
- **Optional Config**:
  ```json
  {
    "researcher_credits": 6,
    "market_credits": 6,
    "coder_credits": 0,
    "browser_credits": 3,
    "stream_config": {
      "recursion_limit": 150
    }
  }
  ```
- **Response**: Server-sent events (SSE) stream with agent updates

### Health Check

- **URL**: `/api/health`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "healthy",
    "service": "market_intelligence_api"
  }
  ```

## Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Demo Interface

A simple demo interface is available at http://localhost:8000/ or http://localhost:8000/static/demo.html.

## Environment Variables

You can customize the application behavior with these environment variables:

- `LANGGRAPH_API_URL`: URL of the LangGraph API service (default: http://localhost:8123)
- `PORT`: Port for the web API server (default: 8000)
- `HOST`: Host for the web API server (default: 0.0.0.0)
- `LOG_LEVEL`: Logging level (default: info)

These can be set in a `.env` file at the project root or as environment variables.

## Notes for Frontend Development

The workflow endpoint uses server-sent events (SSE) for streaming agent responses. 
Here's an example of how to consume this stream in JavaScript:

```javascript
const eventSource = new EventSource('/api/run-workflow');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('New agent update:', data);
  
  // Process agent messages, state changes, etc.
  if (data.message) {
    console.log('Agent message:', data.message);
  }
  
  // Check for final report
  if (data.final_report) {
    console.log('Final report received:', data.final_report);
    eventSource.close(); // Close the connection when complete
  }
};

eventSource.onerror = (error) => {
  console.error('EventSource error:', error);
  eventSource.close();
};
``` 