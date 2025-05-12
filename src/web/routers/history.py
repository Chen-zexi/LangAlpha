import logging
from datetime import datetime
from typing import List, Dict, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from database.models.messages import get_messages_by_session
from database.models.reports import get_all_reports, get_reports_by_session, get_report, get_recent_reports

logger = logging.getLogger(__name__)
router = APIRouter()

# Define Timezones
EST = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

def convert_to_est(dt_obj: datetime) -> datetime:
    if dt_obj.tzinfo is None:  
        dt_obj = dt_obj.replace(tzinfo=UTC)
    elif dt_obj.tzinfo != UTC: 
        dt_obj = dt_obj.astimezone(UTC)
    return dt_obj.astimezone(EST)

@router.get("/api/history/sessions", response_class=JSONResponse)
async def get_sessions():
    """Get a list of all unique session IDs and their associated report titles."""
    try:
        reports = get_all_reports(limit=500)
        
        sessions_dict: Dict[str, Dict[str, Any]] = {}
        for report in reports:
            session_id = report.get("session_id")
            if session_id:
                report_timestamp = report.get("timestamp")
                last_updated_val = report.get("last_updated")

                # Determine the effective timestamp for comparison and storage
                effective_timestamp = last_updated_val if last_updated_val else report_timestamp

                if session_id not in sessions_dict or \
                   (effective_timestamp and sessions_dict[session_id].get("last_updated") and \
                    effective_timestamp > sessions_dict[session_id]["last_updated"]):
                    sessions_dict[session_id] = {
                        "session_id": session_id,
                        "last_updated": effective_timestamp,
                        "title": report.get("title", f"Analysis Session {session_id[:8]}")
                    }
        
        sessions = list(sessions_dict.values())
        sessions.sort(key=lambda x: x.get("last_updated") or datetime.min.replace(tzinfo=UTC), reverse=True)
        
        sessions = sessions[:100]
        
        for session in sessions:
             if isinstance(session.get("last_updated"), datetime):
                session["last_updated"] = convert_to_est(session["last_updated"]).isoformat()
                
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Error fetching sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching sessions: {str(e)}")

@router.get("/api/history/messages/{session_id}", response_class=JSONResponse)
async def get_session_messages(session_id: str):
    """Get all messages for a specific session"""
    try:
        messages = get_messages_by_session(session_id)
        for message in messages:
            if "_id" in message and hasattr(message["_id"], '__str__'):
                message["_id"] = str(message["_id"])
            if isinstance(message.get("timestamp"), datetime):
                message["timestamp"] = convert_to_est(message["timestamp"]).isoformat()
                
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Error fetching messages for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching messages: {str(e)}")

@router.get("/api/history/reports/{session_id}", response_class=JSONResponse)
async def get_session_reports(session_id: str):
    """Get all reports for a specific session (should usually be one)."""
    try:
        reports = get_reports_by_session(session_id)
        for report in reports:
            if "_id" in report and hasattr(report["_id"], '__str__'):
                 report["_id"] = str(report["_id"])
            if isinstance(report.get("timestamp"), datetime):
                report["timestamp"] = convert_to_est(report["timestamp"]).isoformat()
            if isinstance(report.get("last_updated"), datetime):
                report["last_updated"] = convert_to_est(report["last_updated"]).isoformat()
                
        return {"reports": reports}
    except Exception as e:
        logger.error(f"Error fetching reports for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")

@router.get("/api/history/report/{session_id}", response_class=JSONResponse)
async def get_single_report_by_session(session_id: str):
    """Get a specific report by session_id."""
    try:
        report = get_report(session_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Report for session {session_id} not found")
            
        if "_id" in report and hasattr(report["_id"], '__str__'):
             report["_id"] = str(report["_id"])
        if isinstance(report.get("timestamp"), datetime):
            report["timestamp"] = convert_to_est(report["timestamp"]).isoformat()
        if isinstance(report.get("last_updated"), datetime):
            report["last_updated"] = convert_to_est(report["last_updated"]).isoformat()
            
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching report for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching report: {str(e)}")

@router.get("/api/recent-reports", response_class=JSONResponse)
async def get_recent_reports_endpoint(limit: int = 5):
    """Get the most recent reports from MongoDB."""
    logger.info(f"Fetching {limit} recent reports")
    try:
        reports_data = get_recent_reports(limit)
        
        processed_reports = []
        for report_item in reports_data:
            if '_id' in report_item and hasattr(report_item["_id"], '__str__'):
                report_item['_id'] = str(report_item['_id'])
            if 'timestamp' in report_item and isinstance(report_item['timestamp'], datetime):
                report_item['timestamp'] = convert_to_est(report_item['timestamp']).isoformat()
            if 'last_updated' in report_item and isinstance(report_item['last_updated'], datetime):
                report_item['last_updated'] = convert_to_est(report_item['last_updated']).isoformat()
            processed_reports.append(report_item)
        
        return JSONResponse(
            content={"reports": processed_reports},
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error fetching recent reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching recent reports: {str(e)}") 