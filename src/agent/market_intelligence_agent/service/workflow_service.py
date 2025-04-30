import asyncio
import logging
import warnings
import sys
import os
from pprint import pprint


warnings.filterwarnings("ignore", category=FutureWarning)


from ..config import TEAM_MEMBERS
from .streaming_message import streaming_message
from langchain_core.messages import convert_to_messages
from langchain_core.messages import message_to_dict
from datetime import datetime
import json
from ..graph import build_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Default level is INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def enable_debug_logging():
    """Enable debug level logging for more detailed execution information."""
    logging.getLogger("market_intelligence_agent").setLevel(logging.DEBUG)


#logger = logging.getLogger(__name__)

graph = build_graph()
# Removed hardcoded user_input_messages


async def run_workflow(user_query: str):
    """
    Runs the LangGraph workflow with the provided user query.
    
    Args:
        user_query: The user's query string to process
        
    Returns:
        Tuple of (raw_response, final_report)
    """
    if not user_query:
        print("Error: No query provided.")
        return
        
    raw_response = []
    final_report = None
    print("=" * 120)
    print(f"Starting graph stream for query: '{user_query}'...")

    try:
        # Use the client to stream runs for the specific thread ID
        async for chunk in graph.astream(
                input={
                # Constants
                "TEAM_MEMBERS": TEAM_MEMBERS,
                # Runtime Variables
                "messages": [user_query], # Use the provided query
                "current_timestamp": datetime.now(),
                "researcher_credits": 6,
                "market_credits": 6,
                "coder_credits": 0,
                "browser_credits": 3,
            },
            config={
                "recursion_limit": 150
            },
            stream_mode="values"
        ):
            raw_response.append(chunk)
            next_agent = chunk.get('next', None)
            last_agent = chunk.get('last_agent', None)
            final_report = chunk.get('final_report', None)
            if chunk.get("messages", None):
                messages = message_to_dict(chunk.get("messages", None)[-1])
                messages = messages['data']
            if last_agent == "coordinator":
                print('Coordinator handed off the task to the team.')

            if messages:
                streaming_message(messages, next_agent, last_agent)
        print("Graph stream finished.")
        return raw_response, final_report
    except Exception as e:
        print(f"An unexpected error occurred during execution: {e}")
        raise


