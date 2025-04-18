import asyncio
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph # Or the specific AgentExecutor class if known
from langchain_mcp_adapters.client import MultiServerMCPClient
import logging

from market_intelligence_agent.prompts import apply_prompt_template
from market_intelligence_agent.tools import (
    bash_tool,
    python_repl_tool,
)
from market_intelligence_agent.tools.mcp_server import MCP_SERVERS

from .llm import get_llm_by_type
from market_intelligence_agent.config.agents import AGENT_LLM_MAP

logger = logging.getLogger(__name__)

# --- Global Cache for MCP Client and Research Agent ---
_mcp_client_instance: MultiServerMCPClient | None = None
_research_agent_instance: CompiledGraph | None = None
# --- End Global Cache ---

_initialized_coder_agent = None

async def initialize_coder_agent():
    tools = [bash_tool, python_repl_tool]
    return create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["coder"]),
        tools=tools,
        prompt=lambda state: apply_prompt_template("coder", state),
    )

async def get_research_agent() -> CompiledGraph:
    """Provides a research agent instance, initializing/caching the MCP client and agent on first call."""
    global _mcp_client_instance, _research_agent_instance

    if _research_agent_instance:
        logger.debug("Returning cached research agent.")
        return _research_agent_instance

    logger.info("First call to get_research_agent: Initializing MCP client and agent...")
    if _mcp_client_instance is None:
        logger.debug("  Initializing MultiServerMCPClient...")
        _mcp_client_instance = MultiServerMCPClient()
        logger.debug("  Entering MCP client context...")
        await _mcp_client_instance.__aenter__() # Start client background tasks
        logger.debug("  Connecting to MCP servers...")
        connect_tasks = [
            _mcp_client_instance.connect_to_server(name, **params)
            for name, params in MCP_SERVERS.items()
        ]
        await asyncio.gather(*connect_tasks)
        logger.info("  MCP servers connected.")
    
    logger.debug("  Getting MCP tools...")
    mcp_tools = _mcp_client_instance.get_tools()
    logger.info(f"  Obtained {len(mcp_tools)} MCP tools.")
    
    logger.debug("  Creating research agent...")
    _research_agent_instance = create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["researcher"]),
        tools=mcp_tools, 
        prompt=lambda state: apply_prompt_template("researcher", state),
    )
    logger.info("Research agent created and cached.")
        
    return _research_agent_instance 

async def get_coder_agent():
    """Get the initialized coder agent, creating it if necessary."""
    global _initialized_coder_agent
    if _initialized_coder_agent is None:
        _initialized_coder_agent = await initialize_coder_agent()
    return _initialized_coder_agent
