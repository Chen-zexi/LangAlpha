from fastapi import APIRouter, Depends, HTTPException
from typing import Dict

from ..security import require_role
from database.models.user_model import UserRole, UserInDB 

router = APIRouter(
    prefix="/protected",
    tags=["protected_routes"]
)

@router.get("/user-area", response_model=Dict[str, str])
async def get_user_area(
    current_user: UserInDB = Depends(require_role([UserRole.USER, UserRole.ADMIN]))
):
    """Accessible by users with USER or ADMIN role."""
    return {"message": f"Welcome to the user area, {current_user.username}! Your role is {current_user.role.value}."}

@router.get("/admin-only", response_model=Dict[str, str])
async def get_admin_only_area(
    current_user: UserInDB = Depends(require_role([UserRole.ADMIN]))
):
    """Accessible only by users with ADMIN role."""
    return {"message": f"Welcome to the admin-only area, {current_user.username}! Your role is {current_user.role.value}."}

@router.post("/create-report", response_model=Dict[str, str])
async def create_user_report(
    current_user: UserInDB = Depends(require_role([UserRole.USER]))
):
    """An example action that only a standard user can perform, not an admin by default unless explicitly added."""
    return {"message": f"User {current_user.username} is creating a report."} 