import logging
from langgraph.prebuilt import create_react_agent
from typing import Literal, Dict, Any, Optional

from ..graph.types import AgentResult
from ..tools import (
    bash_tool,
    python_code_tool,
    browser_tool,
    python_repl_tool
)
from .llm import get_llm_by_type

logger = logging.getLogger(__name__)


async def get_coder_agent(llm_type: Literal["basic", "reasoning", "economic", "coding"], llm_configs: Optional[Dict[str, Any]] = None):
    tools = [python_repl_tool]
    coder_llm = get_llm_by_type(llm_type, llm_configs)
    return create_react_agent(
        coder_llm,
        tools=tools,
        response_format=AgentResult
    )


async def get_browser_agent(llm_type: Literal["basic", "reasoning", "economic", "coding"], llm_configs: Optional[Dict[str, Any]] = None):
    logger.debug(f"Creating browser agent with LLM type: {llm_type}")
    browser_llm = get_llm_by_type(llm_type, llm_configs)
    browser_agent = create_react_agent(
        browser_llm,
        tools=[browser_tool],
    )
    return browser_agent