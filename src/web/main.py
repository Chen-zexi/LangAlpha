import os
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
import uuid
import yfinance as yf


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from langgraph_sdk import get_client


from agent.market_intelligence_agent.config import TEAM_MEMBERS
from agent.market_intelligence_agent.config.agents import get_agent_llm_map

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

class ModelConfig(BaseModel):
    model: str
    provider: str
    # Add any other LLM params you might want to configure later, e.g., temperature
    # temperature: Optional[float] = None 

class LLMConfigs(BaseModel):
    reasoning: ModelConfig
    basic: ModelConfig
    coding: ModelConfig
    economic: ModelConfig
class WorkflowConfig(BaseModel):
    team_members: Optional[Dict[str, Any]] = None
    researcher_credits: int = 6
    market_credits: int = 6
    coder_credits: int = 0
    browser_credits: int = 3
    stream_config: Optional[StreamConfig] = StreamConfig()
    budget: Optional[Literal["low", "medium", "high"]] = "low"
    llm_configs: Optional[LLMConfigs] = None

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

async def generate_log_messages(message: Optional[Dict[str, Any]], next_agent: Optional[str], last_agent: Optional[str], final_report: Optional[str], report_status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generates structured log messages based on agent state and message content."""
    log_messages = []
    
    if message:
        agent_name = message.get("name")
        content_str = message.get("content")
        
        if agent_name and content_str:
            
            # Special handling for analyst and reporter before trying to parse JSON
            if agent_name == "analyst":
                log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Analyst has finished generating insight."})
            elif agent_name == "reporter":
                # Reporter status will be handled separately based on report_status
                if report_status == "saved":
                    log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Reporter agent has finished and the report has been saved."})
                elif report_status == "error":
                     log_messages.append({"type": "error", "agent": agent_name, "content": f"Reporter agent finished, but there was an error saving the report."})
                else:
                     log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Reporter agent is processing"})
            else:
                # For all other agents, try to parse the content
                try:
                    content = json.loads(content_str) if isinstance(content_str, str) else content_str
                    
                    if agent_name == "planner":
                        if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Plan Title: {content.get('title', 'N/A')}"}) # Keep title for debugging/log
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

                    elif agent_name == "coordinator":
                        if isinstance(content, dict):
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Coordinator processed query and set time range: {content.get('time_range', 'N/A')}"})
                        else:
                            log_messages.append({"type": "agent_output", "agent": agent_name, "content": f"Received coordinator content (non-dict): {content_str}"})

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
        status_message = f"Waiting for {next_agent}..." # Default message
        if next_agent == "planner":
            status_message = 'Planner is thinking'
        elif next_agent == "supervisor":
            status_message = f'Supervisor is evaluating response from {last_agent or "previous agent"}...' # Keep this detail
        elif next_agent == "researcher":
            status_message = 'Researcher is gathering information'
        elif next_agent == "coder":
            status_message = 'Coder is coding'
        elif next_agent == "market":
            status_message = 'Market agent is retrieving market data'
        elif next_agent == "browser":
            status_message = 'Browser agent is browsing the web'
        elif next_agent == "analyst":
            status_message = 'Analyst agent is analyzing the gathered information'
        elif next_agent == "reporter":
             # Don't signal report readiness here; wait for save confirmation
             status_message = 'Reporter agent is preparing the final report'
        elif next_agent == "coordinator":
            status_message = 'Coordinator is processing the query'

        log_messages.append({"type": "status", "agent": next_agent, "content": status_message})


    return log_messages

# Define a new function to format and send the report status update
async def format_report_status_update(session_id: str, status: str, error_message: Optional[str] = None) -> str:
    """Formats an SSE message specifically for report status updates."""
    sse_data = {
        "type": "report_status",
        "session_id": session_id,
        "status": status, # e.g., 'saved', 'error'
    }
    if status == 'error' and error_message:
        sse_data["error_message"] = error_message
    
    return json.dumps(sse_data, cls=DateTimeEncoder)


async def format_chunk_for_streaming(chunk, report_status: Optional[str] = None):
    """Formats a LangGraph chunk into structured log messages for streaming."""
    try:
        messages_data = chunk.data.get("messages", [])
        next_agent = chunk.data.get("next", None)
        last_agent = chunk.data.get("last_agent", None)
        
        # Sanitize messages if necessary (keep existing logic)
        if messages_data:
            for i, msg in enumerate(messages_data):
                if isinstance(msg, dict) and 'content' in msg and isinstance(msg['content'], str):
                    try:
                        json.dumps(msg['content'])
                    except (TypeError, json.JSONDecodeError):
                        msg['content'] = msg['content'].replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                        logger.warning(f"Sanitized problematic content in message from {msg.get('name', 'unknown')}")

        # Use the latest message if available
        latest_message = messages_data[-1] if messages_data else None

        logger.debug(f"Processing chunk: last_agent={last_agent}, next_agent={next_agent}, message={latest_message is not None}")

        # Generate structured log messages, passing the report status
        log_messages = await generate_log_messages(latest_message, next_agent, last_agent, None, report_status=report_status)
        
        # Structure the SSE data
        sse_data = {
            "logs": log_messages,
            "next": next_agent,
            "last_agent": last_agent,
            "messages": [latest_message] if latest_message else []
        }

        # Convert to JSON string
        try:
            json_data = json.dumps(sse_data, cls=DateTimeEncoder)
            logger.debug(f"Streaming chunk size: {len(json_data)} bytes")
            return json_data
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON encoding error: {json_err}. Sanitizing data and retrying.")
            safe_sse_data = {
                "logs": log_messages,
                "next": next_agent,
                "last_agent": last_agent,
                "messages": [] 
            }
            return json.dumps(safe_sse_data, cls=DateTimeEncoder)
    except Exception as e:
        logger.error(f"Error formatting chunk for streaming: {e}", exc_info=True)
        return json.dumps({"error": f"Error formatting chunk: {str(e)}"}) # Keep error reporting

async def stream_workflow_results(query: str, config: WorkflowConfig, session_id: str):
    """Stream results from the LangGraph workflow and save report directly.""" # Updated docstring
    logger.info(f"Starting workflow stream for query: '{query}' with budget: {config.budget}, session_id: {session_id}")
    
    # Use provided session_id, no need to generate a new one here
    
    if config.llm_configs:
        logger.info(f"Using custom LLM configurations provided in request.")
    else:
        logger.info(f"No custom LLM configurations provided, will use defaults based on env vars.")
        
    lg_client, thread_info = await get_lg_client_and_thread()
    
    agent_llm_map = get_agent_llm_map(config.budget)
    logger.debug(f"Using agent LLM map: {agent_llm_map}")
    
    llm_configs_dict = config.llm_configs.model_dump() if config.llm_configs else None
    if llm_configs_dict:
        logger.debug(f"Passing LLM configs to state: {llm_configs_dict}")
        for llm_type, llm_config in llm_configs_dict.items():
            logger.info(f"LLM config for {llm_type}: {llm_config}")
    else:
        logger.warning("No LLM configs provided, using defaults")

    try:
        # Send initial connection message
        initial_message = json.dumps({
            "type": "connection_established",
            "message": "Streaming connection established. Starting analysis...",
            "session_id": session_id
        })
        yield f"data: {initial_message}\n\n"
        
        # Variables to store planner title and final report content
        planner_title = f"Analysis for: {query}" # Default title
        final_report_content = None
        report_saved_or_failed = False # Flag to track if report status was sent
        report_save_status = None # 'saved' or 'error'
        ticker_type = None # Store ticker type from the state
        ticker_info_list: Optional[List[Dict[str, Any]]] = None  # Store tickers from the state, ensure type hint

        async for chunk in lg_client.runs.stream(
            thread_info["thread_id"],
            "market_intelligence_agent",
            input={
                "TEAM_MEMBERS": config.team_members or TEAM_MEMBERS,
                "messages": [query],
                "current_timestamp": datetime.now(),
                "researcher_credits": config.researcher_credits,
                "market_credits": config.market_credits,
                "coder_credits": config.coder_credits,
                "browser_credits": config.browser_credits,
                "agent_llm_map": agent_llm_map, 
                "llm_configs": llm_configs_dict,
            },
            config={
                "recursion_limit": config.stream_config.recursion_limit
            },
            stream_mode=["values", "custom"]
        ):
            try:
                # 1. Extract planner title if available
                messages_data = chunk.data.get("messages", [])
                if messages_data:
                    for message in messages_data:
                        if message and message.get("name") == "planner":
                            content_str = message.get("content", "")
                            try:
                                content_dict = json.loads(content_str) if isinstance(content_str, str) else content_str
                                if isinstance(content_dict, dict) and "title" in content_dict:
                                    planner_title = content_dict["title"]
                                    logger.info(f"Extracted planner title: {planner_title} for session {session_id}")
                            except (json.JSONDecodeError, TypeError):
                                logger.warning(f"Could not parse planner content for title: {content_str}")
                
                # 2. Check for ticker info in the state
                # Get potential updates from the chunk
                chunk_ticker_type = chunk.data.get("ticker_type", None)
                if chunk_ticker_type:
                    ticker_type = chunk_ticker_type.lower() # Update if new value found
                    logger.info(f"Received ticker type update: {ticker_type} for session {session_id}")

                chunk_tickers = chunk.data.get("tickers", None)
                if chunk_tickers:
                    ticker_info_list = chunk_tickers # Update if new value found
                    logger.info(f"Received ticker information update for session {session_id}: {ticker_info_list}")
                
                # 3. Check for final report content in the chunk
                current_final_report = chunk.data.get("final_report", None)
                if current_final_report:
                    final_report_content = current_final_report # Store it
                    logger.info(f"Received final_report content for session {session_id}. Preparing to save.")

                    # --- Start: Ticker Validation before saving ---
                    validated_ticker_info_list = []
                    if ticker_info_list:
                        logger.info(f"Attempting validation for tickers: {ticker_info_list}")
                        possible_exchanges = ["NASDAQ", "NYSE", "AMEX"] # Order to try
                        
                        for ticker_info in ticker_info_list:
                            original_symbol = ticker_info.get('tradingview_symbol') or ticker_info.get('ticker') # Get best guess
                            if not original_symbol:
                                logger.warning(f"Skipping validation for ticker_info with no symbol: {ticker_info}")
                                validated_ticker_info_list.append(ticker_info) # Keep original if no symbol
                                continue

                            base_ticker = original_symbol.split(':')[-1] # Extract base ticker like 'AAPL'
                            validated = False
                            validated_symbol = None

                            # Prioritize provided exchange if available
                            exchanges_to_try = possible_exchanges
                            if ':' in original_symbol:
                                provided_exchange = original_symbol.split(':')[0].upper()
                                if provided_exchange in exchanges_to_try:
                                     # Move provided exchange to the front
                                     exchanges_to_try = [provided_exchange] + [ex for ex in possible_exchanges if ex != provided_exchange]
                                else:
                                     exchanges_to_try = [provided_exchange] + possible_exchanges # Add if unknown

                            logger.debug(f"Validation order for {base_ticker}: {exchanges_to_try}")

                            for exchange in exchanges_to_try:
                                try_symbol = f"{exchange}:{base_ticker}"
                                try:
                                    logger.debug(f"Trying yfinance validation for: {try_symbol}")
                                    yf_ticker = yf.Ticker(base_ticker) # yfinance often prefers base ticker
                                    # Check if info is available and contains a symbol (basic check)
                                    info = yf_ticker.info
                                    if info and info.get('symbol'): 
                                        # Simple validation: if yfinance returns info, assume exchange is likely okay for TradingView too
                                        # We use the exchange prefix format for TradingView consistency
                                        validated_symbol = f"{exchange}:{base_ticker}"
                                        logger.info(f"Validation successful for {base_ticker} on {exchange}. Using: {validated_symbol}")
                                        validated = True
                                        break # Stop trying exchanges once validated
                                    else:
                                         logger.debug(f"No sufficient info from yfinance for {base_ticker} (tried as {try_symbol})")
                                except Exception as yf_error:
                                    logger.warning(f"yfinance error validating {try_symbol}: {yf_error}")
                                    # Continue to next exchange

                            if validated:
                                ticker_info['tradingview_symbol'] = validated_symbol # Update with validated symbol
                            else:
                                logger.warning(f"Could not validate {base_ticker} on {exchanges_to_try}. Keeping original/best guess: {original_symbol}")
                                # Keep original if validation fails, maybe TradingView handles it differently
                                ticker_info['tradingview_symbol'] = original_symbol 
                            
                            validated_ticker_info_list.append(ticker_info)
                    else:
                         validated_ticker_info_list = ticker_info_list # Assign None or empty list if no tickers

                    ticker_info_list = validated_ticker_info_list # Use the validated list going forward
                    # --- End: Ticker Validation ---


                    # 4. Save the report immediately when final_report is received
                    if session_id and planner_title and final_report_content and not report_saved_or_failed:
                        # Add ticker info to metadata if available
                        report_metadata = {
                            "query": query
                        }
                        if ticker_type:
                            report_metadata["ticker_type"] = ticker_type
                        if ticker_info_list: # Use the potentially validated list
                            report_metadata["tickers"] = ticker_info_list
                            
                        report_to_save: Report = {
                            "session_id": session_id,
                            "timestamp": datetime.now(),
                            "title": planner_title,
                            "content": final_report_content,
                            "metadata": report_metadata # Include potentially validated tickers
                        }
                        saved_report = save_report(report_to_save)
                        if saved_report:
                            logger.info(f"Successfully saved/updated report for session {session_id}")
                            report_save_status = "saved"
                        else:
                            logger.error(f"Failed to save report for session {session_id}")
                            report_save_status = "error"
                        report_saved_or_failed = True
                        
                        # Send a specific status update for the report save
                        report_update_message = await format_report_status_update(session_id, report_save_status)
                        yield f"data: {report_update_message}\n\n"
                
                # 5. Format and yield the regular chunk data (logs, next agent, etc.)
                # Pass the report save status to influence reporter log message
                formatted_chunk = await format_chunk_for_streaming(chunk, report_status=report_save_status)
                
                # Add session_id to the formatted chunk before sending
                try:
                    chunk_data = json.loads(formatted_chunk)
                    chunk_data["session_id"] = session_id
                    formatted_chunk = json.dumps(chunk_data)
                except json.JSONDecodeError as json_err:
                    logger.error(f"Error adding session_id to chunk: {json_err}")

                yield f"data: {formatted_chunk}\n\n"
            
            except Exception as e:
                logger.error(f"Error processing chunk: {e}", exc_info=True)
                error_data = json.dumps({
                    "error": "Error processing chunk",
                    "details": str(e),
                    "type": "chunk_error",
                    "session_id": session_id
                })
                yield f"data: {error_data}\n\n"
            
        # Send a final stream complete message (no report content needed here)
        final_message = {
            "type": "stream_complete",
            "message": "Analysis stream complete.",
            "session_id": session_id,
            "report_status": report_save_status if report_saved_or_failed else "not_generated" # Indicate final status
        }
        yield f"data: {json.dumps(final_message)}\n\n"
        
    except Exception as e:
        logger.error(f"Error streaming workflow results for session {session_id}: {e}", exc_info=True)
        # Save error message to MongoDB (keep this)
        try:
            error_database_message: Message = {
                "session_id": session_id,
                "timestamp": datetime.now(),
                "role": "system",
                "content": f"Error during stream: {str(e)}",
                "type": "error",
                "metadata": {
                    "thread_id": thread_info["thread_id"],
                    "error_details": str(e)
                }
            }
            save_message(error_database_message)
        except Exception as db_error:
            logger.error(f"Failed to save stream error message to MongoDB: {db_error}")
        
        # Send stream error to client
        error_message = json.dumps({
            "error": "An error occurred during the analysis stream.",
            "details": str(e),
            "type": "stream_error",
            "session_id": session_id
        })
        yield f"data: {error_message}\n\n"

@app.post("/api/run-workflow")
async def run_workflow_post(request: Request):
    """Initiate the LangGraph workflow and return a run_id for streaming.""" # Updated docstring
    try:
        body = await request.json()
        logger.info(f"Received workflow request with body: {body}")
        
        request_data = body.get("request", {})
        config_data = body.get("config", {})
        logger.info(f"Extracted config_data: {config_data}")
        
        config = WorkflowConfig(**config_data)
        logger.info(f"Validated WorkflowConfig: {config}")
        
        # Extract query
        query = request_data.get("query")
        if not query or not query.strip():
            logger.error("Query field is required and cannot be empty")
            raise HTTPException(status_code=422, detail="Query field is required and cannot be empty")
        
        # Create a unique ID for this workflow run and session
        run_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4()) # Generate a session ID here
        logger.info(f"Created workflow run ID: {run_id}, session ID: {session_id} for query: '{query}'")
        
        # Store necessary data for the stream endpoint
        app.state.workflow_runs = getattr(app.state, "workflow_runs", {})
        app.state.workflow_runs[run_id] = {
            "query": query, 
            "config": config,
            "session_id": session_id # Store the generated session_id
        }
        
        # Return response with run_id and session_id
        response = Response(
            status_code=200,
            content=json.dumps({"run_id": run_id, "session_id": session_id, "status": "initiated"}),
            media_type="application/json"
        )
        stream_url = f"/api/run-workflow/stream/{run_id}"
        response.headers["Content-Location"] = stream_url
        logger.info(f"Returning stream URL: {stream_url} with session_id: {session_id}")
        
        return response
    except HTTPException as http_err:
        logger.error(f"HTTP Exception in run_workflow_post: {http_err.detail}")
        raise # Re-raise HTTPException
    except Exception as e:
        logger.error(f"Error in run_workflow_post: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/run-workflow/stream/{run_id}")
async def run_workflow_stream_get(run_id: str): # Renamed for clarity
    """
    Stream the results of a previously initiated workflow run using SSE.
    """ # Updated docstring
    logger.info(f"Stream requested for run ID: {run_id}")
    
    workflow_runs = getattr(app.state, "workflow_runs", {})
    if run_id not in workflow_runs:
        logger.error(f"Workflow run not found: {run_id}")
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    run_data = workflow_runs[run_id]
    query = run_data["query"]
    config = run_data["config"]
    session_id = run_data["session_id"] # Retrieve the session_id
    logger.info(f"Starting stream for query: '{query}', session_id: {session_id}")
    
    # Stream results
    return StreamingResponse(
        stream_workflow_results(query, config, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )

@app.get("/")
async def home():
    """Redirect to the index page."""
    return RedirectResponse(url="/index")

@app.get("/index")
async def index(request: Request): # Pass request for templates
    """Render the index page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/report")
async def report_page(request: Request, session_id: Optional[str] = None): # Expect session_id
    """Serve the report page, expecting session_id."""
    logger.info(f"Serving report page, session_id from query: {session_id}")
    return templates.TemplateResponse("report.html", {"request": request, "session_id": session_id})

@app.get("/settings")
async def settings(request: Request):
    """Serve the settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/all-reports")
async def all_reports_page(request: Request):
    logger.info(f"Serving all-reports page")
    return templates.TemplateResponse("all-reports.html", {"request": request})

@app.get("/api/health")
async def health_check():
    try:
        # Return a simple health check response
        return {"status": "ok", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

# --- MongoDB History Endpoints --- 

@app.get("/api/history/sessions", response_class=JSONResponse)
async def get_sessions():
    """Get a list of all unique session IDs and their associated report titles.""" # Updated doc
    try:
        # Fetch all reports to get session info (limit might be needed for many reports)
        reports = get_all_reports(limit=500) # Increased limit or implement pagination
        
        sessions_dict = {}
        for report in reports:
            session_id = report.get("session_id")
            if session_id:
                # Store the latest info for each session
                if session_id not in sessions_dict or report["timestamp"] > sessions_dict[session_id]["last_updated"]:
                    sessions_dict[session_id] = {
                        "session_id": session_id,
                        "last_updated": report["timestamp"],
                        "title": report.get("title", f"Analysis Session {session_id[:8]}")
                    }
        
        sessions = list(sessions_dict.values())
        # Sort by timestamp descending (newest first)
        sessions.sort(key=lambda x: x["last_updated"], reverse=True)
        
        # Apply limit after sorting
        sessions = sessions[:100] # Limit the final list size
        
        # Convert datetime for JSON response
        for session in sessions:
             if isinstance(session.get("last_updated"), datetime):
                session["last_updated"] = session["last_updated"].isoformat()
                
        return {"sessions": sessions}
    except Exception as e:
        logging.error(f"Error fetching sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching sessions: {str(e)}")


@app.get("/api/history/messages/{session_id}", response_class=JSONResponse)
async def get_session_messages(session_id: str):
    """Get all messages for a specific session"""
    try:
        messages = get_messages_by_session(session_id)
        for message in messages:
            if "_id" in message:
                message["_id"] = str(message["_id"]) # Keep _id for messages if needed
            if isinstance(message.get("timestamp"), datetime):
                message["timestamp"] = message["timestamp"].isoformat()
                
        return {"messages": messages}
    except Exception as e:
        logging.error(f"Error fetching messages for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching messages: {str(e)}")


@app.get("/api/history/reports/{session_id}", response_class=JSONResponse)
async def get_session_reports(session_id: str):
    """Get all reports for a specific session (should usually be one)."""
    try:
        # Use get_reports_by_session which returns a list
        reports = get_reports_by_session(session_id)
        
        # Prepare reports for JSON response
        for report in reports:
            if "_id" in report: # Keep _id if underlying DB uses it
                 report["_id"] = str(report["_id"])
            if isinstance(report.get("timestamp"), datetime):
                report["timestamp"] = report["timestamp"].isoformat()
            if isinstance(report.get("last_updated"), datetime):
                report["last_updated"] = report["last_updated"].isoformat()
                
        return {"reports": reports}
    except Exception as e:
        logging.error(f"Error fetching reports for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")


@app.get("/api/history/report/{session_id}", response_class=JSONResponse)
async def get_single_report_by_session(session_id: str): # Renamed for clarity
    """Get a specific report by session_id."""
    try:
        report = get_report(session_id) # Use the updated get_report
        if not report:
            raise HTTPException(status_code=404, detail=f"Report for session {session_id} not found")
            
        # Convert fields for JSON response
        if "_id" in report: # If MongoDB adds _id automatically
             report["_id"] = str(report["_id"])
        if isinstance(report.get("timestamp"), datetime):
            report["timestamp"] = report["timestamp"].isoformat()
        if isinstance(report.get("last_updated"), datetime):
            report["last_updated"] = report["last_updated"].isoformat()
            
        return report
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching report for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching report: {str(e)}")


# Add routes for history pages
@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Render the history page."""
    return templates.TemplateResponse("history.html", {"request": request})



@app.get("/api/recent-reports", response_class=JSONResponse)
async def get_recent_reports_endpoint(limit: int = 5):
    """Get the most recent reports from MongoDB."""
    logger.info(f"Fetching {limit} recent reports")
    try:
        reports = get_recent_reports(limit)
        
        for report in reports:
            if '_id' in report:
                report['_id'] = str(report['_id'])
            if 'timestamp' in report and isinstance(report['timestamp'], datetime):
                report['timestamp'] = report['timestamp'].isoformat()
            if 'last_updated' in report and isinstance(report['last_updated'], datetime):
                report['last_updated'] = report['last_updated'].isoformat()
        
        return JSONResponse(
            content={"reports": reports},
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error fetching recent reports: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching recent reports: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server at {API_HOST}:{API_PORT}")
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)