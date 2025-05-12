"""
Report model for storing final generated reports.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from pymongo.collection import Collection
from pymongo import ReturnDocument # Import ReturnDocument for upsert

from ..utils.mongo_client import get_database


class Report(TypedDict):
    """TypedDict for a generated report."""
    session_id: str # This will be our primary identifier
    timestamp: datetime
    title: str
    content: str
    metadata: Optional[Dict[str, Any]]
    # We no longer need a separate _id field if session_id is the primary key


def get_reports_collection() -> Collection:
    """
    Get the MongoDB collection for reports.
    
    Returns:
        Collection: MongoDB collection for reports
    """
    db = get_database()
    return db.reports


def save_report(report: Report) -> Optional[Report]:
    """
    Save a report to the database using session_id as the identifier (upsert).
    If a report with the session_id exists, it will be updated. Otherwise, it will be inserted.
    
    Args:
        report (Report): Report to save or update
        
    Returns:
        Optional[Report]: The saved or updated report document, or None on error.
    """
    collection = get_reports_collection()
    
    # Use session_id as the filter for the upsert operation
    session_id = report.get("session_id")
    if not session_id:
        # Log an error or raise an exception, session_id is required
        print("Error: session_id is required to save a report.") # Replace with logger
        return None

    # Perform an upsert operation
    # This will update the document if one with the session_id exists, or insert it if not.
    # We use $set to update fields and $setOnInsert to set timestamp only on creation.
    result = collection.find_one_and_update(
        {"session_id": session_id},
        {
            "$set": {
                "title": report.get("title"),
                "content": report.get("content"),
                "metadata": report.get("metadata"),
                "last_updated": datetime.now() # Add/update last_updated timestamp
            },
            "$setOnInsert": {
                "session_id": session_id,
                "timestamp": report.get("timestamp", datetime.now()) # Set initial timestamp on insert
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER # Return the modified document
    )
    
    return result


def get_report(session_id: str) -> Optional[Report]:
    """
    Get a specific report by session_id.
    
    Args:
        session_id (str): Session ID of the report to retrieve.
        
    Returns:
        Optional[Report]: The report or None if not found
    """
    # Remove ObjectId import as we are using session_id
    # from bson.objectid import ObjectId 
    
    collection = get_reports_collection()
    # Query using session_id instead of _id
    report = collection.find_one({"session_id": session_id})
    return report


def get_reports_by_session(session_id: str) -> List[Report]:
    """
    Get all reports for a specific session. 
    (Note: With upsert, there should typically only be one report per session)
    
    Args:
        session_id (str): Session ID to filter by
        
    Returns:
        List[Report]: List containing the report (or empty if none)
    """
    collection = get_reports_collection()
    # Query might return multiple if upsert wasn't strictly enforced before,
    # but ideally returns 0 or 1.
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


def delete_report_by_session_id(session_id: str) -> bool:
    """
    Deletes a report from the database by its session_id.

    Args:
        session_id (str): The session_id of the report to delete.

    Returns:
        bool: True if a report was deleted, False otherwise.
    """
    collection = get_reports_collection()
    result = collection.delete_one({"session_id": session_id})
    return result.deleted_count > 0 