import asyncio
import logging
import warnings
import sys
import os

from .streaming_message import streaming_message


warnings.filterwarnings("ignore", category=FutureWarning)


from ..config import TEAM_MEMBERS
from langchain_core.messages import convert_to_messages
from langgraph_sdk import get_client
from datetime import datetime


# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Default level is INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def enable_debug_logging():
    """Enable debug level logging for more detailed execution information."""
    logging.getLogger("market_intelligence_agent").setLevel(logging.DEBUG)


logger = logging.getLogger(__name__)

# LangGraph Client
async def get_lg_client_and_thread():
    lg_client = get_client(url="http://localhost:2024")
    thread_info = await lg_client.threads.create() # This returns a dict
    return lg_client, thread_info

# Removed hardcoded user_input_messages

async def run_workflow(user_query: str):
    """Runs the LangGraph workflow with the provided user query."""
    if not user_query:
        print("Error: No query provided.")
        return
    raw_response = []
    final_report = None
    lg_client, thread_info = await get_lg_client_and_thread()
    print("=" * 120)
    print(f"Starting graph stream for query: '{user_query}'...")
    # Use the client to stream runs for the specific thread ID
    async for chunk in lg_client.runs.stream(
            thread_info["thread_id"], # Get thread_id from the dict
            assistant_id="market_intelligence_agent",
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
        messages = chunk.data.get("messages", None)
        next_agent = chunk.data.get('next', None)
        last_agent = chunk.data.get('last_agent', None)
        final_report = chunk.data.get('final_report', None)
        if messages:
            messages = messages[-1]
        if last_agent == "coordinator":
            print('Coordinator handed off the task to the team.')

        if messages:
            streaming_message(messages, next_agent, last_agent)
    print("Graph stream finished.")
    return raw_response, final_report


