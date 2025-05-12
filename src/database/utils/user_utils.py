from pymongo.database import Database
from passlib.context import CryptContext
from datetime import datetime
from typing import Optional, List

from ..models.user_model import UserInDB, UserCreate, UserRole
from .invitation_code_utils import get_invitation_code_by_code_str, use_invitation_code
from .mongo_client import get_database

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS_COLLECTION = "users"

def get_user_by_username(db: Database = None, username: str = None) -> UserInDB | None:
    if db is None:
        db = get_database()
    user_data = db[USERS_COLLECTION].find_one({"username": username})
    if user_data:
        return UserInDB(**user_data)
    return None

def get_all_users(db: Database = None, invitation_code: Optional[str] = None) -> List[UserInDB]:
    if db is None:
        db = get_database()
    
    query = {}
    if invitation_code:
        query["invitation_code"] = invitation_code
        
    users_data = db[USERS_COLLECTION].find(query)
    return [UserInDB(**user) for user in users_data]

def update_user_role(db: Database, username: str, new_role: UserRole) -> bool:
    """Updates the role of a user specified by username."""
    result = db[USERS_COLLECTION].update_one(
        {"username": username},
        {"$set": {"role": new_role.value}}
    )
    return result.modified_count > 0

def update_refresh_token(
    db: Database, 
    username: str, 
    hashed_refresh_token: Optional[str],
    refresh_token_expires_at: Optional[datetime]
):
    """Stores or clears the refresh token details for a user."""
    update_data = {
        "hashed_refresh_token": hashed_refresh_token,
        "refresh_token_expires_at": refresh_token_expires_at
    }
    db[USERS_COLLECTION].update_one(
        {"username": username},
        {"$set": update_data}
    )

def create_user(db: Database = None, user_in: UserCreate = None) -> UserInDB:
    if db is None:
        db = get_database()
    
    hashed_password = pwd_context.hash(user_in.password)
    
    role = UserRole.VISITOR # Default role
    if user_in.invitation_code:
        invitation_code_obj = get_invitation_code_by_code_str(db=db, code_str=user_in.invitation_code)
        if invitation_code_obj and invitation_code_obj.is_active:
            if invitation_code_obj.uses_left is None or invitation_code_obj.uses_left > 0:
                role = invitation_code_obj.role
                if not use_invitation_code(db=db, code_obj=invitation_code_obj):
                    print(f"Warning: Failed to mark invitation code {invitation_code_obj.code} as used, but role assigned.")

    user_db_data = {
        "username": user_in.username,
        "email": user_in.email,
        "hashed_password": hashed_password,
        "first_name": user_in.first_name,
        "last_name": user_in.last_name,
        "organization": user_in.organization,
        "invitation_code": user_in.invitation_code,
        "role": role
    }
    
    user_db_dict = {k: v for k, v in user_db_data.items() if v is not None}
    
    if "role" not in user_db_dict:
         user_db_dict["role"] = UserRole.VISITOR

    user_db = UserInDB(**user_db_dict)
    
    db[USERS_COLLECTION].insert_one(user_db.model_dump(by_alias=True))
    return user_db

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def delete_user_by_username(db: Database, username: str) -> bool:
    """Deletes a user by their username."""
    if db is None:
        db = get_database()
    
    # Prevent deleting the last admin user
    user_to_delete = get_user_by_username(db=db, username=username)
    if user_to_delete and user_to_delete.role == UserRole.ADMIN:
        admins_count = 0
        all_users = get_all_users(db=db)
        for u in all_users:
            if u.role == UserRole.ADMIN:
                admins_count += 1
        if admins_count <= 1:
            print(f"Attempt to delete the last admin user ('{username}') was blocked.")
            return False 
            
    result = db[USERS_COLLECTION].delete_one({"username": username})
    return result.deleted_count > 0 