from pydantic import BaseModel, Field
from enum import Enum
import uuid
from datetime import datetime
from typing import Optional

from .user_model import UserRole

class InvitationCode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    role: UserRole
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    uses_left: Optional[int] = None

class InvitationCodeCreate(BaseModel):
    role: UserRole
    created_by: Optional[str] = None
    uses_left: Optional[int] = None 