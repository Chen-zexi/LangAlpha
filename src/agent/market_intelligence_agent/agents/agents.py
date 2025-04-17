import asyncio
from langgraph.prebuilt import create_react_agent

from market_intelligence_agent.prompts import apply_prompt_template
from market_intelligence_agent.tools import (
    bash_tool,
    python_repl_tool,
)

from market_intelligence_agent.tools.mcp_server import get_global_mcp_connection

from .llm import get_llm_by_type
from market_intelligence_agent.config.agents import AGENT_LLM_MAP

# Store initialized agents
_initialized_research_agent = None
_initialized_coder_agent = None

# Create agents using configured LLM types
async def initialize_research_agent():
    connection_manager = await get_global_mcp_connection()  # Get the global manager
    tools = await connection_manager.get_tools()
    return create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["researcher"]),
        tools=tools,
        prompt=lambda state: apply_prompt_template("researcher", state),
    )

async def initialize_coder_agent():
    tools = [bash_tool, python_repl_tool]
    return create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["coder"]),
        tools=tools,
        prompt=lambda state: apply_prompt_template("coder", state),
    )

async def get_research_agent():
    """Get the initialized research agent, creating it if necessary."""
    global _initialized_research_agent
    if _initialized_research_agent is None:
        _initialized_research_agent = await initialize_research_agent()
    return _initialized_research_agent

async def get_coder_agent():
    """Get the initialized coder agent, creating it if necessary."""
    global _initialized_coder_agent
    if _initialized_coder_agent is None:
        _initialized_coder_agent = await initialize_coder_agent()
    return _initialized_coder_agent
