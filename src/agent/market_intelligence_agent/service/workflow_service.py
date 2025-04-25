import asyncio
import logging
import warnings
import sys
import os


warnings.filterwarnings("ignore", category=FutureWarning)


from ..config import TEAM_MEMBERS
from langchain_core.messages import convert_to_messages
from langgraph_sdk import get_client
from datetime import datetime
import json

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
    lg_client, thread_info = await get_lg_client_and_thread()
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
        state = chunk.data
        next_agent = chunk.data.get('next', None)
        last_agent = chunk.data.get('last_agent', None)
        if last_agent == "coordinator":
            print('Coordinator handed off the task to the team.')

        if messages:
            print("-" * 120)
            agent_name = messages[-1].get('name', None)
            if agent_name:
                if agent_name == "planner":
                    full_plan = state.get('full_plan', None)
                    print(json.loads(convert_to_messages(messages)[-1].content)['thought'])
                    print(f"Planner handed off the following plan to the supervisor: \n{full_plan}")
                if agent_name == "supervisor":
                    instructions = json.loads(convert_to_messages(messages)[-1].content)
                    print(f"Supervisor assigned the following task to {next_agent}: \n{instructions['task']}")
                if agent_name == "researcher":
                    research_result = json.loads(convert_to_messages(messages)[-1].content)
                    print(f"Researcher has finished the task: {research_result['result_summary']}")
                if agent_name == "coder":
                    coder_result = json.loads(convert_to_messages(messages)[-1].content)
                    print(f"Coder has finished the task: {coder_result['result_summary']}")
                if agent_name == "market":
                    market_result = json.loads(convert_to_messages(messages)[-1].content)
                    print(f"Market agent has finished the task: {market_result['result_summary']}")
        if next_agent:
            print("=" * 120)
            if next_agent == "planner":
                print('Planner is thinking...')
            if next_agent == "supervisor":
                print(f'Supervisor is evaluating response from {last_agent}...')
            if next_agent == "researcher":
                print('Researcher is gathering information...')
            if next_agent == "coder":
                print('Coder is coding...')
            if next_agent == "market":
                print('Market agent is retrieving market data...')
            if next_agent == "browser":
                print('Browser agent is browsing the web...')
            if next_agent == "analyst":
                print('Analyst agent is analyzing the gathered information...')
            if next_agent == "reporter":
                print('Reporter agent is preparing the final report...')
                
    current_state = await lg_client.threads.get_state(thread_info["thread_id"])
    final_report = current_state['values']['final_report']
    print("Graph stream finished.")
    return raw_response, final_report


