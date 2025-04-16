import asyncio
from langgraph.prebuilt import create_react_agent

from src.agent.market_intelligence_agent.prompts import apply_prompt_template
from src.agent.market_intelligence_agent.tools import (
    bash_tool,
    python_repl_tool,
)

from src.agent.market_intelligence_agent.tools.mcp_server import mcp_connection_manager

from .llm import get_llm_by_type
from src.agent.market_intelligence_agent.config.agents import AGENT_LLM_MAP


# Create agents using configured LLM types
async def research_agent():
    connection_manager = await mcp_connection_manager()  # Get the manager
    tools = await connection_manager.get_tools()
    return create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["researcher"]),
        tools=tools,
        prompt=lambda state: apply_prompt_template("researcher", state),
    )

async def coder_agent():
    connection_manager = await mcp_connection_manager()  # Get the manager
    tools = await connection_manager.get_tools()
    return create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["coder"]),
        tools=tools,
        prompt=lambda state: apply_prompt_template("coder", state),
    )

research_agent = asyncio.create_task(research_agent())
coder_agent = asyncio.create_task(coder_agent())
