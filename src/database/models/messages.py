"""
Message model for storing streaming conversation messages.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict, Union
from pymongo.collection import Collection

from ..utils.mongo_client import get_database


class Message(TypedDict):
    """TypedDict for a streaming message."""
    session_id: str
    timestamp: datetime
    role: str  # 'user', 'assistant', 'system'
    content: str
    type: str  # 'agent_message', 'status', 'error', 'plan_step', 'event', etc.
    metadata: Optional[Dict[str, Any]]
    ui_state: Optional[Dict[str, Any]]  # New field for storing UI-specific state


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


def get_messages_by_session_and_type(session_id: str, message_type: Union[str, List[str]]) -> List[Message]:
    """
    Get messages for a specific session filtered by type.
    
    Args:
        session_id (str): Session ID to filter by
        message_type (str or List[str]): Message type(s) to filter by
        
    Returns:
        List[Message]: List of filtered messages
    """
    collection = get_messages_collection()
    
    if isinstance(message_type, list):
        query = {"session_id": session_id, "type": {"$in": message_type}}
    else:
        query = {"session_id": session_id, "type": message_type}
        
    messages = collection.find(query)
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