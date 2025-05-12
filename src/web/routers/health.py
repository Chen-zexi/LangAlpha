import logging
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/health")
async def health_check():
    try:
        return {"status": "ok", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e), "timestamp": datetime.now().isoformat()}
        ) 