import asyncio
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph # Or the specific AgentExecutor class if known
from langchain_mcp_adapters.client import MultiServerMCPClient
import logging

from ..graph.types import AgentResult

from ..prompts import apply_prompt_template
from ..tools import (
    bash_tool,
    python_repl_tool,
    browser_tool,
)
from ..tools.mcp_server_research import MCP_SERVERS_RESEARCH
from ..tools.mcp_server_market import MCP_SERVERS_MARKET
from .llm import get_llm_by_type
from ..config.agents import AGENT_LLM_MAP

logger = logging.getLogger(__name__)

# --- Global Cache for MCP Client and Research Agent ---
_mcp_client_instance_research: MultiServerMCPClient | None = None
_mcp_client_instance_market: MultiServerMCPClient | None = None
_research_agent_instance: CompiledGraph | None = None
_market_agent_instance: CompiledGraph | None = None
# --- End Global Cache ---

_initialized_coder_agent = None

async def initialize_coder_agent():
    tools = [bash_tool, python_repl_tool]
    return create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["coder"]),
        tools=tools,
        prompt=lambda state: apply_prompt_template("coder", state),
        response_format=AgentResult
    )

async def get_research_agent() -> CompiledGraph:
    """Provides a research agent instance, initializing/caching the MCP client and agent on first call."""
    global _mcp_client_instance_research, _research_agent_instance

    if _research_agent_instance:
        logger.debug("Returning cached research agent.")
        return _research_agent_instance

    logger.info("First call to get_research_agent: Initializing MCP client and agent...")
    if _mcp_client_instance_research is None:
        logger.debug("  Initializing MultiServerMCPClient...")
        _mcp_client_instance_research = MultiServerMCPClient()
        logger.debug("  Entering MCP client context...")
        await _mcp_client_instance_research.__aenter__() # Start client background tasks
        logger.debug("  Connecting to MCP servers...")
        connect_tasks = [
            _mcp_client_instance_research.connect_to_server(name, **params)
            for name, params in MCP_SERVERS_RESEARCH.items()
        ]
        await asyncio.gather(*connect_tasks)
        logger.info("  MCP servers connected.")
    
    logger.debug("  Getting MCP tools...")
    mcp_tools = _mcp_client_instance_research.get_tools()
    logger.info(f"  Obtained {len(mcp_tools)} MCP tools.")
    logger.debug("  Creating research agent...")
    _research_agent_instance = create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["researcher"]),
        tools=mcp_tools, 
        prompt=lambda state: apply_prompt_template("researcher", state),
        response_format=AgentResult
    )
    logger.info("Research agent created and cached.")
        
    return _research_agent_instance 

async def get_market_agent() -> CompiledGraph:
    """Provides a research agent instance, initializing/caching the MCP client and agent on first call."""
    global _mcp_client_instance_market, _market_agent_instance

    if _market_agent_instance:
        logger.debug("Returning cached market agent.")
        return _market_agent_instance

    logger.info("First call to get_market_agent: Initializing MCP client and agent...")
    if _mcp_client_instance_market is None:
        logger.debug("  Initializing MultiServerMCPClient...")
        _mcp_client_instance_market = MultiServerMCPClient()
        logger.debug("  Entering MCP client context...")
        await _mcp_client_instance_market.__aenter__() # Start client background tasks
        logger.debug("  Connecting to MCP servers...")
        connect_tasks = [
            _mcp_client_instance_market.connect_to_server(name, **params)
            for name, params in MCP_SERVERS_MARKET.items()
        ]
        await asyncio.gather(*connect_tasks)
        logger.info("  MCP servers connected.")
    
    logger.debug("  Getting MCP tools...")
    mcp_tools = _mcp_client_instance_market.get_tools()
    logger.info(f"  Obtained {len(mcp_tools)} MCP tools.")
    logger.debug("  Creating research agent...")
    _market_agent_instance = create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["market"]),
        tools=mcp_tools, 
        prompt=lambda state: apply_prompt_template("market", state),
        response_format=AgentResult
    )
    logger.info("Market agent created and cached.")
        
    return _market_agent_instance 

async def get_coder_agent():
    """Get the initialized coder agent, creating it if necessary."""
    global _initialized_coder_agent
    if _initialized_coder_agent is None:
        _initialized_coder_agent = await initialize_coder_agent()
    return _initialized_coder_agent

async def get_browser_agent():
    browser_agent = create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["browser"]),
        tools=[browser_tool],
        prompt=lambda state: apply_prompt_template("browser", state),
    )
    return browser_agent

async def shutdown_mcp_clients():
    """Explicitly shuts down the global MCP client instances if they were initialized."""
    global _mcp_client_instance_research, _mcp_client_instance_market
    logger.info("Attempting to shut down global MCP clients sequentially...")
    
    research_client = _mcp_client_instance_research
    market_client = _mcp_client_instance_market
    
    # Clear global refs immediately to prevent reuse during shutdown
    _mcp_client_instance_research = None
    _mcp_client_instance_market = None
    
    shutdown_error = None
    
    if research_client:
        logger.info("  Shutting down research MCP client...")
        try:
            await research_client.__aexit__(None, None, None)
            logger.info("  Research MCP client shut down.")
        except Exception as e:
            logger.error(f"Error shutting down research MCP client: {e}", exc_info=True)
            if not shutdown_error: # Keep the first error
                shutdown_error = e
                
    if market_client:
        logger.info("  Shutting down market MCP client...")
        try:
            await market_client.__aexit__(None, None, None)
            logger.info("  Market MCP client shut down.")
        except Exception as e:
            logger.error(f"Error shutting down market MCP client: {e}", exc_info=True)
            if not shutdown_error: # Keep the first error
                 shutdown_error = e

    if not research_client and not market_client:
        logger.info("No active global MCP clients found to shut down.")
    elif shutdown_error:
        logger.error(f"Error(s) occurred during MCP client shutdown. First error: {shutdown_error}")
        # Optionally re-raise the first error if needed, but logging might be sufficient
        # raise shutdown_error 
    else:
        logger.info("Global MCP clients shut down successfully.")
