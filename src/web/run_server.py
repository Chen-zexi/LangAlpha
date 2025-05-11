"""
Script to run the Market Intelligence API server.
"""

import os
import sys
import uvicorn
from pathlib import Path

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"Loaded environment variables from {env_path}")
except ImportError:
    print("python-dotenv not installed, skipping .env file loading")

if __name__ == "__main__":
    # Load environment variables
    API_PORT = int(os.getenv("PORT", "8000"))
    API_HOST = os.getenv("HOST", "0.0.0.0")
    
    # Print MongoDB connection information (without credentials)
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/")
    mongo_db = os.getenv("MONGODB_DB", "langalpha")
    mongo_host = mongo_uri.split('@')[-1].split('/')[0] if '@' in mongo_uri else mongo_uri.split('//')[1].split('/')[0]
    
    print(f"Starting web API server on {API_HOST}:{API_PORT}")
    print(f"Using LangGraph API URL: {os.getenv('LANGGRAPH_API_URL', 'http://localhost:8123')}")
    print(f"Using MongoDB at {mongo_host} with database '{mongo_db}'")
    
    # Determine the correct app import path based on our environment
    file_dir = Path(__file__).resolve().parent
    if file_dir.name == 'web' and (file_dir.parent / 'agent').exists():
        print("Running in Docker environment with app module structure")
        app_module = "web.main:app"
        
        # Import database to initialize connection
        try:
            import database
            print("Successfully imported database module")
        except ImportError:
            print("Warning: Failed to import database module. MongoDB connection may not be available.")
    else:
        print("Running in local environment with src module structure")
        app_module = "src.web.main:app"
        
        # Import database to initialize connection
        try:
            import src.database
            print("Successfully imported database module")
        except ImportError:
            print("Warning: Failed to import database module. MongoDB connection may not be available.")
    
    print(f"Using app module: {app_module}")
    uvicorn.run(app_module, host=API_HOST, port=API_PORT, reload=True) 