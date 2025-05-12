import os
import logging
from pathlib import Path

# Configuration from environment variables
LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://langgraph-api:8000")
API_PORT = int(os.getenv("PORT", "8000"))
API_HOST = os.getenv("HOST", "0.0.0.0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

# Configure logging with more detailed format
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("market_intelligence_api")

# Log startup information
logger.info(f"Starting Market Intelligence API server")
logger.info(f"LANGGRAPH_API_URL: {LANGGRAPH_API_URL}")
logger.info(f"API_PORT: {API_PORT}")
logger.info(f"API_HOST: {API_HOST}")
logger.info(f"LOG_LEVEL: {LOG_LEVEL}")

# Determine base directory for static and templates relative to this config file
_WEB_DIR = Path(__file__).parent # This will be src/web

static_dir = _WEB_DIR / "static"
if not static_dir.exists():
    logger.warning(f"Static directory not found at {static_dir}. Creating it.")
    static_dir.mkdir(parents=True, exist_ok=True)

templates_dir = _WEB_DIR / "templates"
if not templates_dir.exists():
    logger.warning(f"Templates directory not found at {templates_dir}. Creating it.")
    templates_dir.mkdir(parents=True, exist_ok=True)

# Log the contents of the static directory
try:
    static_files = list(static_dir.glob("**/*"))
    logger.info(f"Static directory ({static_dir}) contents: {[str(f.relative_to(static_dir)) for f in static_files]}")
except Exception as e:
    logger.error(f"Error listing static directory {static_dir}: {e}") 