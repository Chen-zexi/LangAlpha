from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any
from pydantic import BaseModel

from ..security import require_role
from database.models.user_model import UserRole, UserInDB
from database.utils.user_utils import get_all_users, update_user_role, get_user_by_username
from database.models.reports import get_all_reports as get_all_db_reports, delete_report_by_session_id, Report as ReportDict
from database.utils.mongo_client import get_database 
from pymongo.database import Database 

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))]
)

class UserRoleUpdate(BaseModel):
    new_role: UserRole

@router.get("/users", response_model=List[UserInDB])
async def list_users(db: Database = Depends(get_database)):
    """Lists all users. Only accessible by admins."""
    users = get_all_users(db=db)
    return users

@router.post("/users/{username}/role", response_model=Dict[str, str])
async def set_user_role(
    username: str, 
    role_update: UserRoleUpdate,
    db: Database = Depends(get_database)
):
    """Updates the role of a specific user. Only accessible by admins."""
    target_user = get_user_by_username(db=db, username=username)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found")

    if target_user.role == UserRole.ADMIN and role_update.new_role != UserRole.ADMIN:
        admins_count = 0
        all_users = get_all_users(db=db)
        for u in all_users:
            if u.role == UserRole.ADMIN:
                admins_count +=1
        if admins_count <=1 and target_user.username == username :
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the last admin's role.")

    success = update_user_role(db=db, username=username, new_role=role_update.new_role)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user role.")
    
    return {"message": f"Role for user '{username}' updated to {role_update.new_role.value}"}


@router.get("/manage-users", response_class=HTMLResponse)
async def manage_users_page(request: Request):
    if not hasattr(request.app.state, 'templates'):
        raise HTTPException(status_code=500, detail="Templates not configured in app state")
    
    role_values = [role.value for role in UserRole]
    
    return request.app.state.templates.TemplateResponse(
        "admin/manage_users.html", 
        {"request": request, "UserRoleValues": role_values}
    )

@router.get("/reports", response_model=List[ReportDict])
async def list_all_reports(db: Database = Depends(get_database)):
    """Lists all reports. Only accessible by admins."""
    reports = get_all_db_reports()
    return reports

@router.delete("/reports/{session_id}", response_model=Dict[str, str])
async def delete_report(session_id: str, db: Database = Depends(get_database)):
    """Deletes a report by its session_id. Only accessible by admins."""
    deleted = delete_report_by_session_id(session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Report with session_id '{session_id}' not found or already deleted.")
    return {"message": f"Report with session_id '{session_id}' deleted successfully."}

@router.get("/manage-reports", response_class=HTMLResponse)
async def manage_reports_page(request: Request):
    """Serves the HTML page for managing reports."""
    if not hasattr(request.app.state, 'templates'):
        raise HTTPException(status_code=500, detail="Templates not configured in app state")
    return request.app.state.templates.TemplateResponse(
        "admin/manage_reports.html", 
        {"request": request}
    ) 