import os
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import configurations from config.py
from .config import API_HOST, API_PORT, logger, static_dir, templates_dir, LANGGRAPH_API_URL 
# Import routers
from .routers import workflow, history, ui, health, auth_router, protected_router, admin_router

# Create FastAPI app
app = FastAPI(
    title="LangGraph API",
    version="1.0",
    description="API for LangGraph Chatbot",
    # lifespan=lifespan,
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory with proper error handling
try:
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Successfully mounted static directory at {static_dir}")
except Exception as e:
    logger.error(f"Error mounting static directory {static_dir}: {e}")

# Setup templates
templates = Jinja2Templates(directory=str(templates_dir))

# Initialize shared state
app.state.workflow_runs = {}
app.state.templates = templates

# Include routers
app.include_router(workflow.router)
app.include_router(history.router)
app.include_router(ui.router)
app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(protected_router.router)
app.include_router(admin_router.router)

# The following endpoint definitions have been moved to their respective routers:
# - WorkflowRequest, StreamConfig, ModelConfig, LLMConfigs, WorkflowConfig (to schemas.py)
# - DateTimeEncoder (to utils.py)
# - get_lg_client_and_thread (to langgraph_client.py)
# - generate_log_messages (to utils.py)
# - format_report_status_update (to utils.py)
# - format_chunk_for_streaming (to utils.py)
# - stream_with_heartbeat (to langgraph_client.py)
# - stream_workflow_results (to langgraph_client.py)
# - @app.post("/api/run-workflow") (to routers/workflow.py)
# - @app.get("/api/run-workflow/stream/{run_id}") (to routers/workflow.py)
# - @app.get("/") (to routers/ui.py)
# - @app.get("/index") (to routers/ui.py)
# - @app.get("/report") (to routers/ui.py)
# - @app.get("/settings") (to routers/ui.py)
# - @app.get("/all-reports") (to routers/ui.py)
# - @app.get("/api/health") (to routers/health.py)
# - MongoDB History Endpoints (to routers/history.py)
# - @app.get("/history") (to routers/ui.py)
# - @app.get("/api/recent-reports") (to routers/history.py)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server at {API_HOST}:{API_PORT} from main.py")
    uvicorn.run(app, host=API_HOST, port=API_PORT, reload=True)