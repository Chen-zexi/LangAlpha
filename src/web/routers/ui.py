import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
# Jinja2Templates will be initialized in main.py and accessed via request.app.state.templates

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
async def home(request: Request):
    """Redirect to the index page."""
    # templates = request.app.state.templates # Not needed for redirect
    return RedirectResponse(url="/index")

@router.get("/index", response_class=HTMLResponse)
async def index(request: Request):
    """Render the index page."""
    templates = request.app.state.templates
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/ginzu", response_class=HTMLResponse)
async def ginzu_page(request: Request):
    """Serve the Ginzu page."""
    templates = request.app.state.templates
    return templates.TemplateResponse("ginzu.html", {"request": request})

@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request, session_id: Optional[str] = None):
    """Serve the report page, expecting session_id."""
    logger.info(f"Serving report page, session_id from query: {session_id}")
    templates = request.app.state.templates
    return templates.TemplateResponse("report.html", {"request": request, "session_id": session_id})

@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Serve the settings page."""
    templates = request.app.state.templates
    return templates.TemplateResponse("settings.html", {"request": request})

@router.get("/all-reports", response_class=HTMLResponse)
async def all_reports_page(request: Request):
    logger.info(f"Serving all-reports page")
    templates = request.app.state.templates
    return templates.TemplateResponse("all-reports.html", {"request": request})

@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Render the history page."""
    templates = request.app.state.templates
    return templates.TemplateResponse("history.html", {"request": request}) 