import os
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import ClassVar, Optional

# Define a Pydantic BaseSettings class for typed configurations
class Settings(BaseSettings):
    LANGGRAPH_API_URL: str = "http://langgraph-api:8000"
    API_PORT: int = 8000
    API_HOST: str = "0.0.0.0"
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # JWT Settings
    SECRET_KEY: str = "your-super-secret-key-please-change-this-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ACCESS_TOKEN_COOKIE_NAME: str = "langalpha_access_token"
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    REFRESH_TOKEN_COOKIE_NAME: str = "langalpha_refresh_token"

    # MongoDB Settings
    MONGODB_URI: str = "mongodb://mongodb:27017/"
    MONGODB_DB: str = "langalpha"

    # Initial Admin User
    INITIAL_ADMIN_USERNAME: Optional[str] = None # Read from .env

    class Config:
        env_file: ClassVar[str] = ".env"
        env_file_encoding: ClassVar[str] = "utf-8"
        extra: ClassVar[str] = "ignore"

settings = Settings()

LANGGRAPH_API_URL = settings.LANGGRAPH_API_URL
API_PORT = settings.API_PORT
API_HOST = settings.API_HOST
LOG_LEVEL = settings.LOG_LEVEL.upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("market_intelligence_api")

logger.info(f"Starting Market Intelligence API server")
logger.info(f"LANGGRAPH_API_URL: {LANGGRAPH_API_URL}")
logger.info(f"API_PORT: {API_PORT}")
logger.info(f"API_HOST: {API_HOST}")
logger.info(f"LOG_LEVEL: {LOG_LEVEL}")
logger.info(f"ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
logger.info(f"REFRESH_TOKEN_EXPIRE_MINUTES: {settings.REFRESH_TOKEN_EXPIRE_MINUTES}") # Log new setting
logger.info(f"ENVIRONMENT: {settings.ENVIRONMENT}") # Log new setting
if settings.INITIAL_ADMIN_USERNAME:
    logger.info(f"INITIAL_ADMIN_USERNAME: {settings.INITIAL_ADMIN_USERNAME}")
else:
    logger.info("INITIAL_ADMIN_USERNAME: Not set in environment. No automatic admin promotion.")

_WEB_DIR = Path(__file__).parent

static_dir = _WEB_DIR / "static"
if not static_dir.exists():
    logger.warning(f"Static directory not found at {static_dir}. Creating it.")
    static_dir.mkdir(parents=True, exist_ok=True)

templates_dir = _WEB_DIR / "templates"
if not templates_dir.exists():
    logger.warning(f"Templates directory not found at {templates_dir}. Creating it.")
    templates_dir.mkdir(parents=True, exist_ok=True)

try:
    static_files = list(static_dir.glob("**/*"))
    logger.info(f"Static directory ({static_dir}) contents: {[str(f.relative_to(static_dir)) for f in static_files]}")
except Exception as e:
    logger.error(f"Error listing static directory {static_dir}: {e}") 