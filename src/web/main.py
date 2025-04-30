import os
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from langgraph_sdk import get_client


from agent.market_intelligence_agent.config import TEAM_MEMBERS


# Configuration from environment variables
LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://localhost:8123")
API_PORT = int(os.getenv("PORT", "8000"))
API_HOST = os.getenv("HOST", "0.0.0.0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("market_intelligence_api")

# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Create FastAPI app
app = FastAPI(
    title="Market Intelligence Agent API",
    description="API for interacting with the Market Intelligence Agent workflow",
    version="0.1.0"
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Define request models
class WorkflowRequest(BaseModel):
    query: str

class StreamConfig(BaseModel):
    recursion_limit: int = 150

class WorkflowConfig(BaseModel):
    team_members: Optional[Dict[str, Any]] = None
    researcher_credits: int = 6
    market_credits: int = 6
    coder_credits: int = 0
    browser_credits: int = 3
    stream_config: Optional[StreamConfig] = StreamConfig()

# LangGraph client setup
async def get_lg_client_and_thread():
    """Creates a LangGraph client and thread."""
    lg_client = get_client(url=LANGGRAPH_API_URL)
    thread_info = await lg_client.threads.create()
    return lg_client, thread_info

async def format_chunk_for_streaming(chunk):
    """Formats a LangGraph chunk for streaming to the client."""
    messages = chunk.data.get("messages", None)
    next_agent = chunk.data.get("next", None)
    last_agent = chunk.data.get("last_agent", None)
    final_report = chunk.data.get("final_report", None)

    logger.info(f"Streaming chunk: {chunk}")
    
    # Format the response
    response_data = {
        "next_agent": next_agent,
        "last_agent": last_agent,
        "final_report": final_report
    }
    
    # Add the latest message if it exists
    if messages and len(messages) > 0:
        # Pass the full message object to the frontend
        response_data["message"] = messages[-1]
        logger.debug(f"Streaming message: {response_data['message']}")
    
    # Convert to JSON string using custom encoder for datetime objects
    return json.dumps(response_data, cls=DateTimeEncoder)

async def stream_workflow_results(query: str, config: WorkflowConfig):
    """Stream results from the LangGraph workflow."""
    lg_client, thread_info = await get_lg_client_and_thread()
    
    try:
        async for chunk in lg_client.runs.stream(
            thread_info["thread_id"],
            "market_intelligence_agent",
            input={
                # Constants
                "TEAM_MEMBERS": config.team_members or TEAM_MEMBERS,
                # Runtime Variables
                "messages": [query],
                "current_timestamp": datetime.now(),
                "researcher_credits": config.researcher_credits,
                "market_credits": config.market_credits,
                "coder_credits": config.coder_credits,
                "browser_credits": config.browser_credits,
            },
            config={
                "recursion_limit": config.stream_config.recursion_limit
            },
            stream_mode=["values", "custom"]
        ):
            formatted_chunk = await format_chunk_for_streaming(chunk)
            yield f"data: {formatted_chunk}\n\n"
    except Exception as e:
        logger.error(f"Error streaming workflow results: {e}", exc_info=True)
        error_message = json.dumps({"error": "An error occurred while streaming workflow results.", "details": str(e)})
        yield f"data: {error_message}\n\n"

@app.post("/api/run-workflow")
async def run_workflow_post(request: Request, config: WorkflowConfig = WorkflowConfig()):
    """
    Run the market intelligence agent workflow with the provided query.
    
    This endpoint initiates the workflow and returns a reference to the stream endpoint.
    """
    body = await request.json()
    
    # Extract query from the request body
    if "request" in body and "query" in body["request"]:
        query = body["request"]["query"]
    elif "query" in body:
        query = body["query"]
    else:
        raise HTTPException(status_code=422, detail="Query field is required")
    
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Create a unique ID for this workflow run
    import uuid
    run_id = str(uuid.uuid4())
    
    # Store the query and config in the app state for retrieval by the stream endpoint
    app.state.workflow_runs = getattr(app.state, "workflow_runs", {})
    app.state.workflow_runs[run_id] = {"query": query, "config": config}
    
    # Return a response with the Location header for the stream endpoint
    response = Response(status_code=200)
    response.headers["Content-Location"] = f"/api/run-workflow/stream/{run_id}"
    
    return response

@app.get("/api/run-workflow/stream/{run_id}")
async def run_workflow_stream(run_id: str):
    """
    Stream the results of a previously initiated workflow run.
    
    This endpoint is used by EventSource to stream results back to the client.
    """
    # Retrieve the query and config from the app state
    workflow_runs = getattr(app.state, "workflow_runs", {})
    if run_id not in workflow_runs:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    run_data = workflow_runs[run_id]
    query = run_data["query"]
    config = run_data["config"]
    
    # Stream the workflow results
    return StreamingResponse(
        stream_workflow_results(query, config),
        media_type="text/event-stream"
    )

@app.get("/")
async def home():
    """Redirect to the demo page."""
    return RedirectResponse(url="/static/demo.html")

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "market_intelligence_api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True) 