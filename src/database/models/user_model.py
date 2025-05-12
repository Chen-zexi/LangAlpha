from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime # Added for refresh_token_expires_at
from enum import Enum # Added for Role enum

# Define UserRole enum before it is used
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"  # This will be our "basic" user
    PREMIUM_USER = "premium_user"
    VISITOR = "visitor" # Added visitor role

class UserInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: Optional[str] = None # Added email
    hashed_password: str
    first_name: Optional[str] = None # Added first_name
    last_name: Optional[str] = None # Added last_name
    organization: Optional[str] = None # Added organization
    invitation_code: Optional[str] = None # Added invitation_code
    hashed_refresh_token: Optional[str] = None
    refresh_token_expires_at: Optional[datetime] = None
    role: UserRole = UserRole.VISITOR 

class UserCreate(BaseModel):
    username: str
    email: str # Added email
    password: str
    first_name: Optional[str] = None # Added first_name
    last_name: Optional[str] = None # Added last_name
    organization: Optional[str] = None # Added organization
    invitation_code: Optional[str] = None # Added invitation_code