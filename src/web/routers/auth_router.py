from fastapi import APIRouter, Request, Depends, Form, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import logging
from datetime import datetime, timezone
import jwt
from pymongo.database import Database
from typing import Optional

from ..config import settings
from database.utils.user_utils import get_user_by_username, create_user, verify_password, update_refresh_token, pwd_context, update_user_role
from database.models.user_model import UserCreate, UserInDB, UserRole
from database.utils.mongo_client import get_database

from ..security import create_access_token, ACCESS_TOKEN_COOKIE_NAME, create_refresh_token, REFRESH_TOKEN_COOKIE_NAME

logger = logging.getLogger(__name__) # Get a logger instance

# Determine the correct templates directory relative to this file
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login_user(response: Response, username: str = Form(...), password: str = Form(...)):
    db = get_database()
    user = get_user_by_username(db=db, username=username)
    if not user or not verify_password(password, user.hashed_password):
        logger.warning(f"Login failed for user '{username}'. Invalid credentials.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    # --- Temporary promotion logic for initial admin --- START
    if settings.INITIAL_ADMIN_USERNAME and user.username == settings.INITIAL_ADMIN_USERNAME:
        if user.role != UserRole.ADMIN:
            logger.info(f"User '{user.username}' matches INITIAL_ADMIN_USERNAME. Attempting promotion during login.")
            update_user_role(db=db, username=user.username, new_role=UserRole.ADMIN)
            # Re-fetch user to get the updated role for the current session token
            updated_user = get_user_by_username(db=db, username=user.username)
            if updated_user and updated_user.role == UserRole.ADMIN:
                user = updated_user # Use the updated user object for token creation
                logger.info(f"Successfully promoted user '{user.username}' to ADMIN during login.")
            else:
                logger.error(f"Failed to promote or re-fetch user '{user.username}' after role update attempt during login.")
        else:
            logger.debug(f"User '{user.username}' (INITIAL_ADMIN_USERNAME) is already ADMIN.")
    # --- Temporary promotion logic for initial admin --- END
    
    # Prepare data for token creation, including the role
    token_data = {"sub": user.username, "role": user.role.value} 
    
    access_token = create_access_token(data=token_data)
    refresh_token, refresh_token_expires_at = create_refresh_token(data=token_data) # Role also in refresh token for consistency
    
    # Hash the refresh token before storing
    hashed_refresh_token = pwd_context.hash(refresh_token)
    update_refresh_token(
        db=db, 
        username=user.username, 
        hashed_refresh_token=hashed_refresh_token, 
        refresh_token_expires_at=refresh_token_expires_at
    )
    
    cookie_key_access = ACCESS_TOKEN_COOKIE_NAME
    cookie_value_access = access_token
    cookie_key_refresh = REFRESH_TOKEN_COOKIE_NAME
    cookie_value_refresh = refresh_token # Send the raw refresh token in cookie

    cookie_httponly = True
    cookie_samesite_lax = "lax" # For access token
    cookie_samesite_strict = "strict" # For refresh token
    cookie_secure = settings.ENVIRONMENT == "production"
    cookie_path = "/"
    
    redirect_response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    logger.info(f"Setting access token cookie: Key='{cookie_key_access}', HTTPOnly={cookie_httponly}, SameSite='{cookie_samesite_lax}', Secure={cookie_secure}, Path='{cookie_path}'")
    redirect_response.set_cookie(
        key=cookie_key_access,
        value=cookie_value_access,
        httponly=cookie_httponly,
        samesite=cookie_samesite_lax,
        secure=cookie_secure,
        path=cookie_path
    )

    logger.info(f"Setting refresh token cookie: Key='{cookie_key_refresh}', HTTPOnly={cookie_httponly}, SameSite='{cookie_samesite_strict}', Secure={cookie_secure}, Path='{cookie_path}'")
    redirect_response.set_cookie(
        key=cookie_key_refresh,
        value=cookie_value_refresh,
        httponly=cookie_httponly,
        samesite=cookie_samesite_strict, # Use Strict for refresh token
        secure=cookie_secure,
        path=cookie_path,
        expires=refresh_token_expires_at # Set explicit expiry for refresh token cookie
    )
    
    logger.info(f"Login successful for user '{user.username}'. Redirecting to /.")
    return redirect_response

@router.post("/token/refresh")
async def refresh_access_token(request: Request, response: Response, db: Database = Depends(get_database)):
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    logger.debug(f"Refresh token endpoint hit. Cookie '{REFRESH_TOKEN_COOKIE_NAME}': {refresh_token_value[:20] if refresh_token_value else 'None'}...")

    if not refresh_token_value:
        logger.warning("No refresh token found in cookies for /token/refresh.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    try:
        # Decode to get username (sub claim)
        payload = jwt.decode(refresh_token_value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": False}) # Verify expiry server-side with DB record
        username = payload.get("sub")
        if not username:
            logger.warning("Username not found in refresh token payload.")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    except jwt.JWTError as e:
        logger.error(f"JWTError decoding refresh token: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = get_user_by_username(db=db, username=username)
    if not user:
        logger.warning(f"User '{username}' from refresh token not found.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    
    if not user.hashed_refresh_token or user.refresh_token_expires_at is None:
        logger.warning(f"User '{username}' has no stored refresh token or expiry.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found or invalidated")

    if datetime.now(timezone.utc) > user.refresh_token_expires_at:
        logger.warning(f"Refresh token for user '{username}' has expired (DB check).")
        # Optionally, clear the expired token from DB
        update_refresh_token(db, username, None, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    if not pwd_context.verify(refresh_token_value, user.hashed_refresh_token):
        logger.warning(f"Refresh token mismatch for user '{username}'. Possible reuse of stolen token or client/server desync.")
        # Critical security event: invalidate all refresh tokens for this user
        update_refresh_token(db, username, None, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # If all checks pass, issue a new access token
    new_access_token_data = {"sub": user.username, "role": user.role.value}
    new_access_token = create_access_token(data=new_access_token_data)
    
    logger.info(f"Successfully refreshed access token for user '{username}'.")
    
    # Set the new access token cookie
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=new_access_token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
        path="/"
    )
    return {"message": "Access token refreshed successfully"}

@router.post("/logout")
async def logout_user(response: Response, request: Request, db: Database = Depends(get_database)):
    
    access_token_value = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    username_to_logout = None

    if access_token_value:
        try:
            payload = jwt.decode(access_token_value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username_to_logout = payload.get("sub")
        except jwt.JWTError:
            logger.warning("Could not decode access token during logout, proceeding to clear cookies.")

    if username_to_logout:
        logger.info(f"Invalidating refresh token for user '{username_to_logout}'")
        update_refresh_token(db, username_to_logout, None, None)
    else:
        logger.warning("No user context for logout, only clearing cookies.")

    redirect_response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    logger.info(f"Deleting access token cookie: {ACCESS_TOKEN_COOKIE_NAME}")
    redirect_response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path="/")
    logger.info(f"Deleting refresh token cookie: {REFRESH_TOKEN_COOKIE_NAME}")
    redirect_response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME, path="/")
    
    return redirect_response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    organization: Optional[str] = Form(None),
    invitation_code: Optional[str] = Form(None)
):
    db = get_database()
    existing_user_by_username = get_user_by_username(db=db, username=username)
    if existing_user_by_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    user_create = UserCreate(
        username=username, 
        email=email,
        password=password, 
        first_name=first_name,
        last_name=last_name,
        organization=organization,
        invitation_code=invitation_code
    )
    created_user = create_user(db=db, user_in=user_create) # Get the created user object
    
    # Check for initial admin promotion
    if settings.INITIAL_ADMIN_USERNAME and created_user.username == settings.INITIAL_ADMIN_USERNAME:
        if created_user.role != UserRole.ADMIN:
            logger.info(f"Promoting user '{created_user.username}' to ADMIN based on INITIAL_ADMIN_USERNAME setting.")
            update_user_role(db=db, username=created_user.username, new_role=UserRole.ADMIN)
        else:
            logger.info(f"User '{created_user.username}' is already ADMIN or INITIAL_ADMIN_USERNAME matches an existing admin.")
            
    # Redirect to login page after successful registration
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND) 