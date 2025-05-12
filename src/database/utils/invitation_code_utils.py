from pymongo.database import Database
from typing import Optional, List

from ..models.invitation_code_model import InvitationCode, InvitationCodeCreate, UserRole
from .mongo_client import get_database

INVITATION_CODES_COLLECTION = "invitation_codes"

def create_invitation_code(db: Database, code_in: InvitationCodeCreate, created_by: Optional[str] = None) -> InvitationCode:
    """Creates and stores a new invitation code in the database."""
    if db is None:
        db = get_database()
    
    new_code = InvitationCode(
        role=code_in.role,
        created_by=created_by,
        uses_left=code_in.uses_left
    )
    
    db[INVITATION_CODES_COLLECTION].insert_one(new_code.model_dump(by_alias=True))
    return new_code

def get_invitation_code_by_code_str(db: Database, code_str: str) -> Optional[InvitationCode]:
    """Retrieves an invitation code by its string value."""
    if db is None:
        db = get_database()
    
    code_data = db[INVITATION_CODES_COLLECTION].find_one({"code": code_str})
    if code_data:
        return InvitationCode(**code_data)
    return None

def use_invitation_code(db: Database, code_obj: InvitationCode) -> bool:
    """
    Marks an invitation code as used.
    Decrements 'uses_left' if it's a limited-use code.
    Sets 'is_active' to False if uses_left becomes 0 or if it's a single-use (None for uses_left originally interpreted as unlimited, but can be made single use here).
    For simplicity, if uses_left is None (unlimited), it remains active.
    If uses_left is a number, it's decremented. If it reaches 0, is_active becomes False.
    """
    if db is None:
        db = get_database()

    if not code_obj.is_active:
        return False # Already inactive

    update_fields = {}
    if code_obj.uses_left is not None:
        if code_obj.uses_left > 0:
            update_fields["uses_left"] = code_obj.uses_left - 1
            if update_fields["uses_left"] == 0:
                update_fields["is_active"] = False
        else:
            if code_obj.is_active:
                update_fields["is_active"] = False 

    if not update_fields:
        return True

    result = db[INVITATION_CODES_COLLECTION].update_one(
        {"code": code_obj.code},
        {"$set": update_fields}
    )
    return result.modified_count > 0

def list_invitation_codes(db: Database) -> List[InvitationCode]:
    """Lists all invitation codes from the database."""
    if db is None:
        db = get_database()
    
    codes_data = db[INVITATION_CODES_COLLECTION].find().sort("created_at", -1)
    return [InvitationCode(**code) for code in codes_data]

def delete_invitation_code(db: Database, code_str: str) -> bool:
    """Deletes an invitation code by its string value."""
    if db is None:
        db = get_database()
    result = db[INVITATION_CODES_COLLECTION].delete_one({"code": code_str})
    return result.deleted_count > 0 