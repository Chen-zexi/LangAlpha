import os
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from langgraph_sdk import get_client


from agent.market_intelligence_agent.config import TEAM_MEMBERS

# Import MongoDB models
from database.models.messages import Message, save_message, get_messages_by_session, clear_messages_by_session
from database.models.reports import Report, save_report, get_report, get_reports_by_session, get_all_reports, get_recent_reports


# Configuration from environment variables
LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://langgraph-api:8000")
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

# Check templates directory
templates_dir = Path(__file__).parent / "templates"
if not templates_dir.exists():
    logger.warning(f"Templates directory not found at {templates_dir}. Creating it.")
    templates_dir.mkdir(parents=True, exist_ok=True)

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

# Setup templates
templates = Jinja2Templates(directory=str(templates_dir))

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

async def stream_workflow_results(query: str, config: WorkflowConfig, session_id: str = None):
    """Stream results from the LangGraph workflow."""
    logger.info(f"Starting workflow stream for query: '{query}'")
    lg_client, thread_info = await get_lg_client_and_thread()
    
    # Generate a session ID for this workflow run if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"Created new session ID: {session_id} for query: '{query}'")
    else:
        logger.info(f"Using provided session ID: {session_id} for query: '{query}'")
    
    try:
        # Send an initial message to confirm the connection is established
        initial_message = json.dumps({
            "type": "connection_established",
            "message": "Streaming connection established. Starting analysis...",
            "session_id": session_id
        })
        yield f"data: {initial_message}\n\n"
        
        # Track the final report content and planner title
        final_report_content = None
        planner_title = f"{query}"  # Default title based on query
        
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
            
            # Add session_id to the chunk for client-side tracking
            chunk_data = json.loads(formatted_chunk)
            chunk_data["session_id"] = session_id
            
            # Extract planner title if available
            if "messages" in chunk_data and chunk_data["messages"]:
                for message in chunk_data["messages"]:
                    if message and message.get("name") == "planner":
                        try:
                            content = message.get("content", "")
                            if isinstance(content, str):
                                content_dict = json.loads(content)
                            else:
                                content_dict = content
                                
                            if isinstance(content_dict, dict) and "title" in content_dict:
                                planner_title = content_dict["title"]
                                logger.info(f"Extracted planner title: {planner_title}")
                                # Add the title to the chunk data for frontend use
                                chunk_data["planner_title"] = planner_title
                        except (json.JSONDecodeError, TypeError, AttributeError) as e:
                            logger.warning(f"Could not extract planner title: {e}")
            
            formatted_chunk = json.dumps(chunk_data)
            
            # Check if this chunk contains a final report
            if "final_report" in chunk_data and chunk_data["final_report"]:
                final_report_content = chunk_data["final_report"]
                logger.info(f"Final report detected in stream chunk for session {session_id}")
            
            # Also check for reporter agent completion which might indicate report is ready
            if chunk_data.get("logs"):
                for log in chunk_data["logs"]:
                    if log.get("agent") == "reporter" and log.get("content") and "finished the task" in log.get("content"):
                        logger.info(f"Reporter agent finished task for session {session_id}")
                        
                        # If we don't already have a final report, generate one from the latest messages
                        if not final_report_content and len(chunk_data.get("messages", [])) > 0:
                            # Use the latest content as the report
                            latest_message = chunk_data["messages"][-1]
                            if latest_message and "content" in latest_message:
                                try:
                                    # Try to parse the content if it's JSON
                                    reporter_content = latest_message["content"]
                                    if isinstance(reporter_content, str):
                                        try:
                                            reporter_json = json.loads(reporter_content)
                                            if isinstance(reporter_json, dict) and "report" in reporter_json:
                                                final_report_content = reporter_json["report"]
                                                logger.info(f"Extracted report from reporter JSON content for session {session_id}")
                                        except json.JSONDecodeError:
                                            # If not JSON, use as-is
                                            final_report_content = reporter_content
                                            logger.info(f"Using reporter raw content as report for session {session_id}")
                                    else:
                                        final_report_content = str(reporter_content)
                                        logger.info(f"Using reporter non-string content as report for session {session_id}")
                                except Exception as e:
                                    logger.error(f"Error extracting report from reporter message: {e}")
            
            yield f"data: {formatted_chunk}\n\n"
            
        # Send a final message to indicate the stream is complete
        final_message = json.dumps({
            "type": "stream_complete",
            "message": "Analysis stream complete.",
            "session_id": session_id,
            "planner_title": planner_title  # Include the planner title in the final message
        })
        yield f"data: {final_message}\n\n"
        
    except Exception as e:
        logger.error(f"Error streaming workflow results: {e}", exc_info=True)
        
        # Save error message to MongoDB for critical error tracking
        try:
            error_database_message: Message = {
                "session_id": session_id,
                "timestamp": datetime.now(),
                "role": "system",
                "content": f"Error: {str(e)}",
                "type": "error",
                "metadata": {
                    "thread_id": thread_info["thread_id"],
                    "error_details": str(e)
                }
            }
            save_message(error_database_message)
        except Exception as db_error:
            logger.error(f"Failed to save error message to MongoDB: {db_error}")
        
        # Send error to client
        error_message = json.dumps({
            "error": "An error occurred while streaming workflow results.",
            "details": str(e),
            "type": "stream_error",
            "session_id": session_id
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
        
        # Create a unique ID for this workflow run and session
        run_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())  # Generate a session ID for MongoDB
        logger.info(f"Created workflow run ID: {run_id}, session ID: {session_id} for query: '{query}'")
        
        # Store the query, config, and session_id in the app state for retrieval by the stream endpoint
        app.state.workflow_runs = getattr(app.state, "workflow_runs", {})
        app.state.workflow_runs[run_id] = {
            "query": query, 
            "config": config,
            "session_id": session_id
        }
        
        # Return a response with the Content-Location header for the stream endpoint
        response = Response(
            status_code=200,
            content=json.dumps({"run_id": run_id, "session_id": session_id, "status": "initiated"}),
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
    session_id = run_data.get("session_id")  # Get session_id if available
    logger.info(f"Starting stream for query: '{query}', session_id: {session_id}")
    
    # Stream the workflow results with appropriate headers for SSE
    return StreamingResponse(
        stream_workflow_results(query, config, session_id),
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
    """Redirect to the index page."""
    return RedirectResponse(url="/index")

@app.get("/index")
async def index():
    """Render the index page."""
    return templates.TemplateResponse("index.html", {"request": {}})

@app.get("/report")
async def report(request: Request, report_id: str = None):
    """Render the report page."""
    if not report_id:
        # If no report_id is provided, redirect to home
        return RedirectResponse(url="/")
    
    # We'll pass the report_id to the template, which will fetch the report data via API
    return templates.TemplateResponse("report.html", {"request": request, "report_id": report_id})

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy", "service": "market_intelligence_api"}

@app.post("/api/create-report")
async def create_report_endpoint(request: Request):
    """
    Create a report from the frontend data and save it to MongoDB.
    
    This endpoint is called directly from the frontend when a report is generated.
    """
    try:
        data = await request.json()
        
        # Extract data with defaults
        content = data.get("content", "")
        
        # Use planner title if provided, otherwise use default title or query-based title
        planner_title = data.get("planner_title")
        query = data.get("metadata", {}).get("query", "")
        
        if planner_title:
            title = planner_title
        else:
            title = data.get("title", f"Analysis for: {query}")
        
        metadata = data.get("metadata", {})
        
        # Generate a session ID if not provided
        session_id = data.get("session_id", f"session_{uuid.uuid4()}")
        
        # Create report object
        report = {
            "session_id": session_id,
            "timestamp": datetime.now(),
            "title": title,
            "content": content,
            "metadata": metadata
        }
        
        # Save to database
        report_id = save_report(report)
        logger.info(f"Created report with ID: {report_id} from frontend request, using title: {title}")
        
        # Return success with the report ID
        return JSONResponse(
            content={"success": True, "report_id": str(report_id)},
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error creating report from frontend: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

# If static files aren't being served correctly, provide direct access to HTML files
@app.get("/direct-index")
async def direct_index():
    """Direct HTML response for index page if static files aren't working."""
    logger.info("Direct index page access attempted")
    try:
        index_path = static_dir / "index.html"
        if index_path.exists():
            with open(index_path, "r") as f:
                content = f.read()
            return HTMLResponse(content)
        else:
            logger.error(f"Index file not found at {index_path}")
            return HTMLResponse("<html><body><h1>Index file not found</h1><p>Check server logs for details.</p></body></html>")
    except Exception as e:
        logger.error(f"Error serving direct index: {e}")
        return HTMLResponse(f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>")

# New endpoints for MongoDB integration

@app.get("/api/history/sessions", response_class=JSONResponse)
async def get_sessions():
    """Get a list of all unique session IDs"""
    try:
        reports = get_all_reports(limit=100)
        # Extract unique session IDs from reports
        sessions = list({report["session_id"]: {
            "session_id": report["session_id"],
            "last_updated": report["timestamp"],
            "title": report.get("title", "Untitled Report")
        } for report in reports}.values())
        
        # Sort by timestamp descending (newest first)
        sessions.sort(key=lambda x: x["last_updated"], reverse=True)
        
        return {"sessions": sessions}
    except Exception as e:
        logging.error(f"Error fetching sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching sessions: {str(e)}")


@app.get("/api/history/messages/{session_id}", response_class=JSONResponse)
async def get_session_messages(session_id: str):
    """Get all messages for a specific session"""
    try:
        messages = get_messages_by_session(session_id)
        # Convert MongoDB ObjectId to string for JSON serialization
        for message in messages:
            if "_id" in message:
                message["_id"] = str(message["_id"])
            if isinstance(message.get("timestamp"), datetime):
                message["timestamp"] = message["timestamp"].isoformat()
                
        return {"messages": messages}
    except Exception as e:
        logging.error(f"Error fetching messages for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching messages: {str(e)}")


@app.get("/api/history/reports/{session_id}", response_class=JSONResponse)
async def get_session_reports(session_id: str):
    """Get all reports for a specific session"""
    try:
        reports = get_reports_by_session(session_id)
        # Convert MongoDB ObjectId to string for JSON serialization
        for report in reports:
            if "_id" in report:
                report["_id"] = str(report["_id"])
            if isinstance(report.get("timestamp"), datetime):
                report["timestamp"] = report["timestamp"].isoformat()
                
        return {"reports": reports}
    except Exception as e:
        logging.error(f"Error fetching reports for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")


@app.get("/api/history/report/{report_id}", response_class=JSONResponse)
async def get_single_report(report_id: str):
    """Get a specific report by ID"""
    try:
        report = get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
            
        # Convert MongoDB ObjectId to string for JSON serialization
        if "_id" in report:
            report["_id"] = str(report["_id"])
        if isinstance(report.get("timestamp"), datetime):
            report["timestamp"] = report["timestamp"].isoformat()
            
        return report
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching report {report_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching report: {str(e)}")


# Add a route for history page
@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Render the history page."""
    return templates.TemplateResponse("history.html", {"request": request})


# Add a route for viewing a specific session
@app.get("/history/{session_id}", response_class=HTMLResponse)
async def session_history_page(request: Request, session_id: str):
    """Render the session history page for a specific session."""
    return templates.TemplateResponse("session_history.html", {"request": request, "session_id": session_id})



async def stream_graph_response(input_text: str, session_id: str, streaming_handler=None):
    """
    This function should be updated to save each message to MongoDB as it's received
    """
    # ... existing code ...
    
    try:
        message_data: Message = {
            "session_id": session_id,
            "timestamp": datetime.now(),
            "role": "system",  # Update according to message role
            "content": "message content",  # The actual content
            "type": "text",  # Message type (text, image, etc.)
            "metadata": {}  # Additional metadata
        }
        save_message(message_data)
        
    except Exception as e:
        logging.error(f"Error in stream_graph_response: {str(e)}")
        raise
    
# ... rest of existing code ...

# Update the report generation endpoint to save to MongoDB
async def create_report(report_data: dict):
    """
    Create a report from the final data.
    
    Args:
        report_data (dict): The final report data
        
    Returns:
        dict: The created report with ID
    """
    try:
        # Extract data
        session_id = report_data.get("session_id", f"session_{uuid.uuid4()}")
        content = report_data.get("content", "")
        title = report_data.get("title", "Investment Report")
        
        # Extract query from metadata or use a default
        query = "Investment Analysis"
        metadata = report_data.get("metadata", {})
        if isinstance(metadata, dict) and "query" in metadata:
            query = metadata["query"]
        elif "query" in report_data:
            query = report_data["query"]
            # Add query to metadata if metadata exists but query is not in it
            if isinstance(metadata, dict) and "query" not in metadata:
                metadata["query"] = query
        
        # Create report object
        report = {
            "session_id": session_id,
            "timestamp": datetime.now(),
            "title": f"Report: {query[:50]}{'...' if len(query) > 50 else ''}",
            "content": content,
            "metadata": metadata
        }
        
        # Save to database
        report_id = save_report(report)
        logger.info(f"Created report with ID: {report_id}")
        
        # Return created report
        return {"id": report_id, "report": report}
    except Exception as e:
        logger.error(f"Error creating report: {e}")
        raise

@app.get("/api/recent-reports", response_class=JSONResponse)
async def get_recent_reports_endpoint(limit: int = 5):
    """
    Get the most recent reports from MongoDB.
    
    Args:
        limit (int, optional): Maximum number of reports to return. Defaults to 5.
        
    Returns:
        JSONResponse: List of recent reports with their IDs
    """
    try:
        recent_reports = get_recent_reports(limit)
        
        # Convert MongoDB ObjectId to string and datetime to ISO format for JSON serialization
        for report in recent_reports:
            if '_id' in report:
                report['_id'] = str(report['_id'])
            if 'timestamp' in report and isinstance(report['timestamp'], datetime):
                report['timestamp'] = report['timestamp'].isoformat()
        
        return JSONResponse(
            content={"reports": recent_reports},
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error fetching recent reports: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching recent reports: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server at {API_HOST}:{API_PORT}")
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)