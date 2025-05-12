import json
import uuid
import logging

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse

from ..schemas import WorkflowConfig # Relative import from parent directory's schemas module
from ..langgraph_client import stream_workflow_results # Relative import for langgraph_client

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/run-workflow")
async def run_workflow_post(request: Request):
    """Initiate the LangGraph workflow and return a run_id for streaming."""
    try:
        body = await request.json()
        logger.info(f"Received workflow request with body: {body}")
        
        request_data = body.get("request", {})
        config_data = body.get("config", {})
        logger.info(f"Extracted config_data: {config_data}")
        
        # Validate config_data using Pydantic model
        try:
            config = WorkflowConfig(**config_data)
        except Exception as pydantic_error:
            logger.error(f"Pydantic validation error for WorkflowConfig: {pydantic_error}")
            raise HTTPException(status_code=422, detail=f"Invalid workflow configuration: {pydantic_error}")

        logger.info(f"Validated WorkflowConfig: {config}")
        
        query = request_data.get("query")
        if not query or not query.strip():
            logger.error("Query field is required and cannot be empty")
            raise HTTPException(status_code=422, detail="Query field is required and cannot be empty")
        
        run_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        logger.info(f"Created workflow run ID: {run_id}, session ID: {session_id} for query: '{query}'")
        
        # Access app.state through request.app.state
        if not hasattr(request.app.state, "workflow_runs"):
            request.app.state.workflow_runs = {}
        request.app.state.workflow_runs[run_id] = {
            "query": query, 
            "config": config,
            "session_id": session_id
        }
        
        response_content = {"run_id": run_id, "session_id": session_id, "status": "initiated"}
        response = Response(
            status_code=200,
            content=json.dumps(response_content),
            media_type="application/json"
        )
        stream_url = f"/api/run-workflow/stream/{run_id}"
        response.headers["Content-Location"] = stream_url
        logger.info(f"Returning stream URL: {stream_url} with session_id: {session_id}")
        
        return response
    except HTTPException as http_err:
        logger.error(f"HTTP Exception in run_workflow_post: {http_err.detail}")
        raise
    except Exception as e:
        logger.error(f"Error in run_workflow_post: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/api/run-workflow/stream/{run_id}")
async def run_workflow_stream_get(run_id: str, request: Request): # Added request to access app.state
    """
    Stream the results of a previously initiated workflow run using SSE.
    """
    logger.info(f"Stream requested for run ID: {run_id}")
    
    workflow_runs = getattr(request.app.state, "workflow_runs", {})
    if run_id not in workflow_runs:
        logger.error(f"Workflow run not found: {run_id}")
        raise HTTPException(status_code=404, detail="Workflow run not found")
    
    run_data = workflow_runs[run_id]
    query = run_data["query"]
    config = run_data["config"]
    session_id = run_data["session_id"]
    logger.info(f"Starting stream for query: '{query}', session_id: {session_id}")
    
    return StreamingResponse(
        stream_workflow_results(query, config, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*", # Consider making this configurable
        }
    ) 