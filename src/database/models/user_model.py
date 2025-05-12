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

class UserInDB(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    hashed_password: str
    hashed_refresh_token: Optional[str] = None
    refresh_token_expires_at: Optional[datetime] = None
    role: UserRole = UserRole.USER # Added role field with default

class UserCreate(BaseModel):
    username: str
    password: str
    # We could add role here if we want to specify it on creation, 
    # otherwise it defaults to UserRole.USER from UserInDB 