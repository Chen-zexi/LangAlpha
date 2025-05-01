import os
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from langgraph_sdk import get_client


from agent.market_intelligence_agent.config import TEAM_MEMBERS


# Configuration from environment variables
LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://localhost:8123")
API_PORT = int(os.getenv("PORT", "8000"))
API_HOST = os.getenv("HOST", "0.0.0.0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

# Configure logging with more detailed format
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("market_intelligence_api")

# Log startup information
logger.info(f"Starting Market Intelligence API server")
logger.info(f"LANGGRAPH_API_URL: {LANGGRAPH_API_URL}")
logger.info(f"API_PORT: {API_PORT}")
logger.info(f"API_HOST: {API_HOST}")
logger.info(f"LOG_LEVEL: {LOG_LEVEL}")

# Check static directory
static_dir = Path(__file__).parent / "static"
if not static_dir.exists():
    logger.warning(f"Static directory not found at {static_dir}. Creating it.")
    static_dir.mkdir(parents=True, exist_ok=True)

# Check for web directory which may be used in Docker
web_dir = Path("/app/web")
if web_dir.exists():
    logger.info(f"Web directory found at {web_dir}")
    if not os.path.exists(static_dir):
        logger.info(f"Linking {web_dir} to {static_dir}")
        os.symlink(web_dir, static_dir)
    else:
        logger.info(f"Using existing static directory at {static_dir}")

# Log the contents of the static directory
try:
    static_files = list(static_dir.glob("**/*"))
    logger.info(f"Static directory contents: {[str(f.relative_to(static_dir)) for f in static_files]}")
except Exception as e:
    logger.error(f"Error listing static directory: {e}")

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

# Mount static files directory with proper error handling
try:
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Successfully mounted static directory at {static_dir}")
except Exception as e:
    logger.error(f"Error mounting static directory: {e}")

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
    logger.debug("Creating LangGraph client and thread")
    try:
        lg_client = get_client(url=LANGGRAPH_API_URL)
        thread_info = await lg_client.threads.create()
        logger.debug(f"Created thread: {thread_info}")
        return lg_client, thread_info
    except Exception as e:
        logger.error(f"Error creating LangGraph client and thread: {e}")
        raise

async def generate_log_messages(message: Optional[Dict[str, Any]], next_agent: Optional[str], last_agent: Optional[str], final_report: Optional[str]) -> List[Dict[str, Any]]:
    """Generates structured log messages based on agent state and message content."""
    log_messages = []
    
    if message:
        agent_name = message.get("name")
        content_str = message.get("content")
        
        if agent_name and content_str:
            log_messages.append({"type": "separator", "content": "-" * 120})
            
            # Special handling for analyst and reporter before trying to parse JSON
            if agent_name == "analyst":
                log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Analyst has finished generating insight."})
            elif agent_name == "reporter":
                log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Reporter agent has finished the task."})
            else:
                # For all other agents, try to parse the content
                try:
                    content = json.loads(content_str) if isinstance(content_str, str) else content_str
                    
                    if agent_name == "planner":
                        if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Plan Title: {content.get('title', 'N/A')}"})
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Thought: {content.get('thought', 'N/A')}"})
                            log_messages.append({"type": "status", "content": f"Planner handed off the following plan to the supervisor:"})
                            for step in content.get('steps', []):
                                 log_messages.append({"type": "plan_step", "agent": step.get('agent'), "content": {
                                     "Task": step.get('task'),
                                     "Agent": step.get('agent'),
                                     "Description": step.get('description'),
                                     "Note": step.get('note')
                                 }})
                        else:
                             log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received planner content (non-dict): {content_str}"})


                    elif agent_name == "supervisor":
                         if isinstance(content, dict):
                            log_messages.append({"type": "status", "content": f"Supervisor assigned the following task to {next_agent or 'N/A'}: \n{content.get('task', 'N/A')}"})
                         else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received supervisor content (non-dict): {content_str}"})


                    elif agent_name == "researcher":
                        if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Researcher finished: {content.get('result_summary', 'No summary provided.')}"})
                        else:
                             log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received researcher content (non-dict): {content_str}"})

                    elif agent_name == "coder":
                         if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Coder finished: {content.get('result_summary', 'No summary provided.')}"})
                         else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received coder content (non-dict): {content_str}"})

                    elif agent_name == "market":
                         if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Market agent finished: {content.get('result_summary', 'No summary provided.')}"})
                         else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received market content (non-dict): {content_str}"})
                    
                    else: # Handle other or unknown agent names
                        log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"{agent_name.capitalize()} content: {content_str}"})

                except json.JSONDecodeError:
                    log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"{agent_name.capitalize()} raw content: {content_str}"})
                except Exception as e:
                    log_messages.append({"type": "error", "content": f"Error processing message from {agent_name}: {e}"})
        
        elif agent_name: # Content is None or empty
             log_messages.append({"type": "status", "content": f"Received empty message from {agent_name}."})


    if next_agent:
        log_messages.append({"type": "separator", "content": "=" * 120})
        status_message = f"Waiting for {next_agent}..." # Default message
        if next_agent == "planner":
            status_message = 'Planner is thinking...'
        elif next_agent == "supervisor":
            status_message = f'Supervisor is evaluating response from {last_agent or "previous agent"}...'
        elif next_agent == "researcher":
            status_message = 'Researcher is gathering information...'
        elif next_agent == "coder":
            status_message = 'Coder is coding...'
        elif next_agent == "market":
            status_message = 'Market agent is retrieving market data...'
        elif next_agent == "browser":
            status_message = 'Browser agent is browsing the web...'
        elif next_agent == "analyst":
            status_message = 'Analyst agent is analyzing the gathered information...'
        elif next_agent == "reporter" and last_agent != "reporter":
             status_message = 'Reporter agent is preparing the final report...'
        elif next_agent == "reporter" and last_agent == "reporter":
             status_message = 'Reporter agent is finalizing the report...' # Handle consecutive reporter calls

        log_messages.append({"type": "status", "agent": next_agent, "content": status_message})

    if final_report:
         log_messages.append({"type": "separator", "content": "*" * 120})
         log_messages.append({"type": "final_report", "content": final_report})

    return log_messages

async def format_chunk_for_streaming(chunk):
    """Formats a LangGraph chunk into structured log messages for streaming."""
    try:
        messages_data = chunk.data.get("messages", [])
        next_agent = chunk.data.get("next", None)
        last_agent = chunk.data.get("last_agent", None)
        final_report = chunk.data.get("final_report", None)

        # Use the latest message if available
        latest_message = messages_data[-1] if messages_data else None

        logger.debug(f"Processing chunk: last_agent={last_agent}, next_agent={next_agent}, message={latest_message is not None}, final_report={final_report is not None}")

        # Generate structured log messages
        log_messages = await generate_log_messages(latest_message, next_agent, last_agent, final_report)
        
        # Include both logs and the original data for more flexibility
        sse_data = {
            "logs": log_messages,
            "next": next_agent,
            "last_agent": last_agent,
            "final_report": final_report,
            "messages": [latest_message] if latest_message else [] # Include latest message only to avoid large payloads
        }

        # Convert to JSON string using custom encoder for datetime objects
        json_data = json.dumps(sse_data, cls=DateTimeEncoder)
        logger.debug(f"Streaming chunk size: {len(json_data)} bytes")
        return json_data
    except Exception as e:
        logger.error(f"Error formatting chunk for streaming: {e}", exc_info=True)
        return json.dumps({"error": f"Error formatting chunk: {str(e)}"})

async def stream_workflow_results(query: str, config: WorkflowConfig):
    """Stream results from the LangGraph workflow."""
    logger.info(f"Starting workflow stream for query: '{query}'")
    lg_client, thread_info = await get_lg_client_and_thread()
    
    try:
        # Send an initial message to confirm the connection is established
        initial_message = json.dumps({
            "type": "connection_established",
            "message": "Streaming connection established. Starting analysis..."
        })
        yield f"data: {initial_message}\n\n"
        
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
            
        # Send a final message to indicate the stream is complete
        final_message = json.dumps({
            "type": "stream_complete",
            "message": "Analysis stream complete."
        })
        yield f"data: {final_message}\n\n"
        
    except Exception as e:
        logger.error(f"Error streaming workflow results: {e}", exc_info=True)
        error_message = json.dumps({
            "error": "An error occurred while streaming workflow results.",
            "details": str(e),
            "type": "stream_error"
        })
        yield f"data: {error_message}\n\n"

@app.post("/api/run-workflow")
async def run_workflow_post(request: Request, config: WorkflowConfig = WorkflowConfig()):
    """
    Run the market intelligence agent workflow with the provided query.
    
    This endpoint initiates the workflow and returns a reference to the stream endpoint.
    """
    try:
        body = await request.json()
        logger.info(f"Received workflow request: {body}")
        
        # Extract query from the request body
        if "request" in body and "query" in body["request"]:
            query = body["request"]["query"]
        elif "query" in body:
            query = body["query"]
        else:
            logger.error("Query field not found in request body")
            raise HTTPException(status_code=422, detail="Query field is required")
        
        if not query or not query.strip():
            logger.error("Empty query received")
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Create a unique ID for this workflow run
        import uuid
        run_id = str(uuid.uuid4())
        logger.info(f"Created workflow run ID: {run_id} for query: '{query}'")
        
        # Store the query and config in the app state for retrieval by the stream endpoint
        app.state.workflow_runs = getattr(app.state, "workflow_runs", {})
        app.state.workflow_runs[run_id] = {"query": query, "config": config}
        
        # Return a response with the Content-Location header for the stream endpoint
        response = Response(
            status_code=200,
            content=json.dumps({"run_id": run_id, "status": "initiated"}),
            media_type="application/json"
        )
        stream_url = f"/api/run-workflow/stream/{run_id}"
        response.headers["Content-Location"] = stream_url
        logger.info(f"Returning stream URL: {stream_url}")
        
        return response
    except Exception as e:
        logger.error(f"Error in run_workflow_post: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/run-workflow/stream/{run_id}")
async def run_workflow_stream(run_id: str):
    """
    Stream the results of a previously initiated workflow run.
    
    This endpoint is used by EventSource to stream results back to the client.
    """
    logger.info(f"Stream requested for run ID: {run_id}")
    
    # Retrieve the query and config from the app state
    workflow_runs = getattr(app.state, "workflow_runs", {})
    if run_id not in workflow_runs:
        logger.error(f"Workflow run not found: {run_id}")
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    run_data = workflow_runs[run_id]
    query = run_data["query"]
    config = run_data["config"]
    logger.info(f"Starting stream for query: '{query}'")
    
    # Stream the workflow results with appropriate headers for SSE
    return StreamingResponse(
        stream_workflow_results(query, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # For Nginx compatibility
            "Access-Control-Allow-Origin": "*",  # CORS for SSE
        }
    )

@app.get("/")
async def home():
    """Redirect to the demo page."""
    logger.debug("Home endpoint accessed, redirecting to demo page")
    return RedirectResponse(url="/static/demo.html")

@app.get("/demo")
async def demo():
    """Direct access to demo page."""
    logger.debug("Demo endpoint accessed, redirecting to demo page")
    return RedirectResponse(url="/static/demo.html")

@app.get("/report")
async def report():
    """Direct access to report page."""
    logger.debug("Report endpoint accessed, redirecting to report page")
    return RedirectResponse(url="/static/report.html")

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy", "service": "market_intelligence_api"}

# If static files aren't being served correctly, provide direct access to HTML files
@app.get("/direct-demo")
async def direct_demo():
    """Direct HTML response for demo page if static files aren't working."""
    logger.info("Direct demo page access attempted")
    try:
        demo_path = static_dir / "demo.html"
        if demo_path.exists():
            with open(demo_path, "r") as f:
                content = f.read()
            return HTMLResponse(content)
        else:
            logger.error(f"Demo file not found at {demo_path}")
            return HTMLResponse("<html><body><h1>Demo file not found</h1><p>Check server logs for details.</p></body></html>")
    except Exception as e:
        logger.error(f"Error serving direct demo: {e}")
        return HTMLResponse(f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server at {API_HOST}:{API_PORT}")
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)