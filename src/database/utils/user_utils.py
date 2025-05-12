from pymongo.database import Database
from passlib.context import CryptContext
from datetime import datetime # Added for refresh token expiry
from typing import Optional, List # Added List

from ..models.user_model import UserInDB, UserCreate, UserRole # Added UserRole
from .mongo_client import get_database

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS_COLLECTION = "users"

def get_user_by_username(db: Database = None, username: str = None) -> UserInDB | None:
    if db is None:
        db = get_database()
    user_data = db[USERS_COLLECTION].find_one({"username": username})
    if user_data:
        return UserInDB(**user_data)
    return None

def get_all_users(db: Database = None) -> List[UserInDB]:
    if db is None:
        db = get_database()
    users_data = db[USERS_COLLECTION].find()
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
    user_db = UserInDB(username=user_in.username, hashed_password=hashed_password)
    
    db[USERS_COLLECTION].insert_one(user_db.model_dump(by_alias=True))
    return user_db

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password) 