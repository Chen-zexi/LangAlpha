from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
import logging # Added for logging

from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer # We might not use this directly if using cookies
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings # This will now import the Settings instance
from database.utils.user_utils import get_user_by_username
from database.models.user_model import UserInDB, UserRole # Added UserRole
from database.utils.mongo_client import get_database

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
ACCESS_TOKEN_COOKIE_NAME = settings.ACCESS_TOKEN_COOKIE_NAME
REFRESH_TOKEN_EXPIRE_MINUTES = settings.REFRESH_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_COOKIE_NAME = settings.REFRESH_TOKEN_COOKIE_NAME

logger = logging.getLogger(__name__)

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, datetime]:
    to_encode = data.copy()
    if expires_delta:
        expire_datetime = datetime.now(timezone.utc) + expires_delta
    else:
        expire_datetime = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire_datetime})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire_datetime

async def get_current_user_from_token(request: Request, db = Depends(get_database)) -> UserInDB:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    logger.debug(f"Attempting to get current user. Cookie '{ACCESS_TOKEN_COOKIE_NAME}': {token}")

    if not token:
        logger.warning(f"No token found in cookies. Redirecting to login.")
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            detail="Not authenticated",
            headers={"Location": "/login"}
        )
    credentials_exception = HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail="Could not validate credentials",
        headers={"Location": "/login"}
    )
    try:
        logger.debug(f"Decoding token: {token} with key: {SECRET_KEY[:10]}... and algo: {ALGORITHM}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role_str: str = payload.get("role")
        logger.debug(f"Token decoded. Username: {username}, Role: {role_str}")
        
        if username is None:
            logger.warning("Username not found in token payload. Redirecting to login.")
            raise credentials_exception
        
        try:
            user_role = UserRole(role_str) if role_str else None
        except ValueError:
            logger.warning(f"Invalid role value '{role_str}' in token payload. Redirecting to login.")
            raise credentials_exception
            
        token_data = TokenData(username=username, role=user_role)
    except JWTError as e:
        logger.error(f"JWTError during token decoding: {e}. Redirecting to login.")
        raise credentials_exception
    
    user = get_user_by_username(db=db, username=token_data.username)
    logger.debug(f"User lookup for username '{token_data.username}': {'Found' if user else 'Not Found'}")
    if user is None:
        logger.warning(f"User '{token_data.username}' not found in database. Redirecting to login.")
        raise credentials_exception
    
    if token_data.role:
        user.role = token_data.role
    elif user.role:
        logger.warning(f"Role not found in token for user '{user.username}', using role from DB: {user.role}")
    else:
        logger.error(f"Role not found in token or DB for user '{user.username}'. Critical issue.")
        raise credentials_exception
        
    return user

async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user_from_token)
) -> UserInDB:
    return current_user

async def get_optional_current_user(request: Request, db = Depends(get_database)) -> Optional[UserInDB]:
    try:
        return await get_current_user_from_token(request, db)
    except HTTPException:
        return None 

def require_role(allowed_roles: list[UserRole]):
    """Dependency that checks if the current user has one of the allowed roles."""
    async def role_checker(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
        if current_user.role not in allowed_roles:
            logger.warning(
                f"User '{current_user.username}' with role '{current_user.role.value}' tried to access a route restricted to roles: {[r.value for r in allowed_roles]}."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have sufficient permissions to access this resource."
            )
        logger.debug(f"User '{current_user.username}' with role '{current_user.role.value}' granted access for roles: {[r.value for r in allowed_roles]}.")
        return current_user
    return role_checker 