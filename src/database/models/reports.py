"""
Report model for storing final generated reports.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict
from pymongo.collection import Collection

from ..utils.mongo_client import get_database


class Report(TypedDict):
    """TypedDict for a generated report."""
    session_id: str
    timestamp: datetime
    title: str
    content: str
    metadata: Optional[Dict[str, Any]]
    

def get_reports_collection() -> Collection:
    """
    Get the MongoDB collection for reports.
    
    Returns:
        Collection: MongoDB collection for reports
    """
    db = get_database()
    return db.reports


def save_report(report: Report) -> str:
    """
    Save a report to the database. Checks for duplicate reports before saving.
    
    Args:
        report (Report): Report to save
        
    Returns:
        str: ID of the inserted report or existing report if duplicate found
    """
    collection = get_reports_collection()
    
    # Check if a similar report already exists for this session/query
    # We'll check based on session_id (if available) and content similarity
    existing_report = None
    if "session_id" in report and report["session_id"]:
        # First try to find by session_id 
        session_reports = list(collection.find({"session_id": report["session_id"]}))
        
        # If we have reports for this session, check content similarity
        if session_reports:
            for existing in session_reports:
                # If content is identical or very similar (first 100 chars match), consider it a duplicate
                if (report["content"] == existing["content"] or 
                    (len(report["content"]) > 100 and 
                     len(existing["content"]) > 100 and
                     report["content"][:100] == existing["content"][:100])):
                    existing_report = existing
                    break
    
    # If no duplicate found, insert the new report
    if existing_report is None:
        result = collection.insert_one(report)
        return str(result.inserted_id)
    else:
        # Return the ID of the existing report
        return str(existing_report["_id"])


def get_report(report_id: str) -> Optional[Report]:
    """
    Get a specific report by ID.
    
    Args:
        report_id (str): Report ID
        
    Returns:
        Optional[Report]: The report or None if not found
    """
    from bson.objectid import ObjectId
    
    collection = get_reports_collection()
    report = collection.find_one({"_id": ObjectId(report_id)})
    return report


def get_reports_by_session(session_id: str) -> List[Report]:
    """
    Get all reports for a specific session.
    
    Args:
        session_id (str): Session ID to filter by
        
    Returns:
        List[Report]: List of reports
    """
    collection = get_reports_collection()
    reports = collection.find({"session_id": session_id})
    return list(reports)


def get_all_reports(limit: int = 100) -> List[Report]:
    """
    Get all reports with pagination.
    
    Args:
        limit (int, optional): Maximum number of reports to return. Defaults to 100.
        
    Returns:
        List[Report]: List of reports
    """
    collection = get_reports_collection()
    reports = collection.find().sort("timestamp", -1).limit(limit)
    return list(reports)


def get_recent_reports(limit: int = 3) -> List[Report]:
    """
    Get the most recent reports ordered by timestamp.
    
    Args:
        limit (int, optional): Maximum number of reports to return. Defaults to 3.
        
    Returns:
        List[Report]: List of recent reports
    """
    collection = get_reports_collection()
    reports = collection.find().sort("timestamp", -1).limit(limit)
    return list(reports) 