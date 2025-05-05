"""
MongoDB client connection utility.
"""

import os
import logging
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Set up logger
logger = logging.getLogger(__name__)

def get_mongodb_client() -> MongoClient:
    """
    Get a MongoDB client using environment variables.
    
    Returns:
        MongoClient: MongoDB client instance
    """
    try:
        mongo_uri = os.getenv('MONGODB_URI', 'mongodb://mongodb:27017/')
        logger.debug(f"Connecting to MongoDB at: {mongo_uri}")
        
        # Add server selection timeout to fail faster if MongoDB is not reachable
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Verify the connection works by issuing a server ping
        client.admin.command('ping')
        logger.debug("Successfully connected to MongoDB")
        
        return client
    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failure: {e}")
        raise
    except ServerSelectionTimeoutError as e:
        logger.error(f"MongoDB server selection timeout: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        raise


def get_database(db_name: str = None) -> Database:
    """
    Get a MongoDB database instance.
    
    Args:
        db_name (str, optional): Database name. If not provided, uses the MONGODB_DB
            environment variable or defaults to 'langalpha'.
    
    Returns:
        Database: MongoDB database instance
    """
    if db_name is None:
        db_name = os.getenv('MONGODB_DB', 'langalpha')
    
    logger.debug(f"Using database: {db_name}")
    client = get_mongodb_client()
    return client[db_name] 