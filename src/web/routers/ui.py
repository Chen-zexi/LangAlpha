import logging
from typing import Optional
import os

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from ..security import get_current_active_user
from database.models.user_model import UserInDB 

logger = logging.getLogger(__name__)


WEB_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
router = APIRouter()

@router.get("/")
async def home(request: Request):
    """Redirect to the index page."""
    return RedirectResponse(url="/index")

@router.get("/index", response_class=HTMLResponse)
async def index(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Render the index page."""
    return templates.TemplateResponse("index.html", {"request": request, "user": current_user})

@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Serve the report page, expecting session_id."""
    logger.info(f"Serving report page, session_id from query: {current_user.id}")
    return templates.TemplateResponse("report.html", {"request": request, "user": current_user})

@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Serve the settings page."""
    return templates.TemplateResponse("settings.html", {"request": request, "user": current_user})

@router.get("/all-reports", response_class=HTMLResponse)
async def all_reports_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    logger.info(f"Serving all-reports page")
    return templates.TemplateResponse("all-reports.html", {"request": request, "user": current_user})

@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Render the history page."""
    return templates.TemplateResponse("history.html", {"request": request, "user": current_user}) 