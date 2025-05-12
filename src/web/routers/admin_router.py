from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from ..security import require_role
from database.models.user_model import UserRole, UserInDB
from database.utils.user_utils import get_all_users, update_user_role, get_user_by_username, delete_user_by_username
from database.models.reports import get_all_reports as get_all_db_reports, delete_report_by_session_id, Report as ReportDict
from database.models.invitation_code_model import InvitationCode, InvitationCodeCreate
from database.utils.invitation_code_utils import (
    create_invitation_code as db_create_invitation_code,
    list_invitation_codes as db_list_invitation_codes,
    delete_invitation_code as db_delete_invitation_code,
    get_invitation_code_by_code_str as db_get_invitation_code_by_code_str
)
from database.utils.mongo_client import get_database 
from pymongo.database import Database 

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role([UserRole.ADMIN]))]
)

# Route for the main admin dashboard
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    """Serves the main admin dashboard page."""
    if not hasattr(request.app.state, 'templates'):
        raise HTTPException(status_code=500, detail="Templates not configured in app state")
    # Pass UserRole to the template for the dropdown
    return request.app.state.templates.TemplateResponse(
        "admin/admin_dashboard.html", 
        {"request": request, "UserRole": UserRole} # Pass the UserRole enum itself
    )

class UserRoleUpdate(BaseModel):
    new_role: UserRole

@router.get("/users", response_model=List[UserInDB])
async def list_users(db: Database = Depends(get_database), invitation_code: Optional[str] = None):
    """Lists all users. Only accessible by admins. Can be filtered by invitation_code."""
    users = get_all_users(db=db, invitation_code=invitation_code)
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

@router.delete("/users/{username}", response_model=Dict[str, str])
async def delete_user(username: str, db: Database = Depends(get_database)):
    """Deletes a user by their username. Only accessible by admins."""
    target_user = get_user_by_username(db=db, username=username)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found.")

    success = delete_user_by_username(db=db, username=username)
    if not success:
        if target_user.role == UserRole.ADMIN:
            all_users = get_all_users(db=db) 
            admins_count = sum(1 for u in all_users if u.role == UserRole.ADMIN and u.username != username) 
            is_potentially_last_admin = True
            is_potentially_last_admin = True 
            users_after_attempt = get_all_users(db=db)
            current_admins_still_exist = any(u.role == UserRole.ADMIN for u in users_after_attempt)
            is_last_admin_deleted = not current_admins_still_exist and any(u.username == username for u in get_all_users(db=db)) 

            if target_user.role == UserRole.ADMIN:
                 db_users = get_all_users(db=db)
                 db_admins_count = sum(1 for u in db_users if u.role == UserRole.ADMIN)
                 if db_admins_count <= 1 and any(u.username == username for u in db_users if u.role == UserRole.ADMIN):
                     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last admin user.")
        
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete user '{username}'. It might be the last admin or an unknown error occurred.")
    
    return {"message": f"User '{username}' deleted successfully."}

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

# --- Invitation Code Endpoints --- 

class InvitationCodeGenerateRequest(BaseModel):
    role: UserRole
    uses_left: Optional[int] = None

@router.post("/invitation-codes/generate", response_model=InvitationCode)
async def generate_invitation_code(
    payload: InvitationCodeGenerateRequest,
    current_admin_user: UserInDB = Depends(require_role([UserRole.ADMIN])),
    db: Database = Depends(get_database)
):
    """Generates a new invitation code."""
    created_by_username = current_admin_user.username

    code_create_data = InvitationCodeCreate(
        role=payload.role,
        uses_left=payload.uses_left,
        created_by=created_by_username
    )
    new_code = db_create_invitation_code(db=db, code_in=code_create_data, created_by=created_by_username)
    if not new_code:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate invitation code.")
    return new_code

@router.get("/invitation-codes", response_model=List[InvitationCode])
async def get_invitation_codes(db: Database = Depends(get_database)):
    """Lists all invitation codes."""
    codes = db_list_invitation_codes(db=db)
    return codes

@router.delete("/invitation-codes/{code_str}", response_model=Dict[str, str])
async def delete_single_invitation_code(code_str: str, db: Database = Depends(get_database)):
    """Deletes an invitation code by its string value."""
    existing_code = db_get_invitation_code_by_code_str(db=db, code_str=code_str)
    if not existing_code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invitation code '{code_str}' not found.")

    success = db_delete_invitation_code(db=db, code_str=code_str)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invitation code '{code_str}' not found or could not be deleted.")
    return {"message": f"Invitation code '{code_str}' deleted successfully."} 