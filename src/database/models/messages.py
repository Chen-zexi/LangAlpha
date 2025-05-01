"""
Message model for storing streaming conversation messages.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict
from pymongo.collection import Collection

from ..utils.mongo_client import get_database


class Message(TypedDict):
    """TypedDict for a streaming message."""
    session_id: str
    timestamp: datetime
    role: str
    content: str
    type: str
    metadata: Optional[Dict[str, Any]]


def get_messages_collection() -> Collection:
    """
    Get the MongoDB collection for messages.
    
    Returns:
        Collection: MongoDB collection for messages
    """
    db = get_database()
    return db.messages


def save_message(message: Message) -> str:
    """
    Save a message to the database.
    
    Args:
        message (Message): Message to save
        
    Returns:
        str: ID of the inserted message
    """
    collection = get_messages_collection()
    result = collection.insert_one(message)
    return str(result.inserted_id)


def get_messages_by_session(session_id: str) -> List[Message]:
    """
    Get all messages for a specific session.
    
    Args:
        session_id (str): Session ID to filter by
        
    Returns:
        List[Message]: List of messages
    """
    collection = get_messages_collection()
    messages = collection.find({"session_id": session_id})
    return list(messages)


def clear_messages_by_session(session_id: str) -> int:
    """
    Delete all messages for a specific session.
    
    Args:
        session_id (str): Session ID to delete
        
    Returns:
        int: Number of deleted messages
    """
    collection = get_messages_collection()
    result = collection.delete_many({"session_id": session_id})
    return result.deleted_count 