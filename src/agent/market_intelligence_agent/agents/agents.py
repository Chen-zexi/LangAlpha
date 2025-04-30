from langgraph.prebuilt import create_react_agent
import logging

from ..graph.types import AgentResult

from ..prompts import apply_prompt_template
from ..tools import (
    bash_tool,
    python_repl_tool,
    browser_tool,
)
from .llm import get_llm_by_type
from ..config.agents import AGENT_LLM_MAP

logger = logging.getLogger(__name__)

# --- Global Cache for Agent ---
_initialized_coder_agent = None

async def initialize_coder_agent():
    tools = [bash_tool, python_repl_tool]
    return create_react_agent(
        get_llm_by_type(AGENT_LLM_MAP["coder"]),
        tools=tools,
        prompt=lambda state: apply_prompt_template("coder", state),
        response_format=AgentResult
    )

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