from typing import Literal, Dict, Any
from .env import BUDGET # Keep for default/fallback if needed
import logging

logger = logging.getLogger(__name__)

# Define available LLM types
LLMType = Literal["basic", "reasoning", "economic", "coding"]

# Define default maps for different budget levels
DEFAULT_LOW_BUDGET_MAP: dict[str, LLMType] = {
    "coordinator": "economic",  
    "planner": "economic",  
    "supervisor": "economic",  
    "researcher": "economic",  
    "coder": "economic",   
    "reporter": "economic",
    "analyst": "economic",
    "browser": "economic",
    "market": "economic",
    "budget": "low",
}
    
DEFAULT_MEDIUM_BUDGET_MAP: dict[str, LLMType] = {
    "coordinator": "basic",  
    "planner": "basic",  
    "supervisor": "basic",  
    "researcher": "basic",  
    "coder": "basic",   
    "reporter": "basic",
    "analyst": "basic",
    "browser": "basic",
    "market": "basic",
    "budget": "medium",
}

DEFAULT_HIGH_BUDGET_MAP: dict[str, LLMType] = {
    "coordinator": "basic",  
    "planner": "reasoning",  
    "supervisor": "basic",  
    "researcher": "coding",
    "coder": "coding",
    "reporter": "basic",
    "analyst": "basic",
    "browser": "basic",
    "market": "coding",
    "budget": "high",
}


def get_agent_llm_map(budget_level: str = "medium") -> Dict[str, Any]:
    """Returns the appropriate agent LLM mapping based on the budget level."""
    budget_level = budget_level.lower()
    if budget_level == "low":
        logger.info("Using LOW budget LLM map.")
        return DEFAULT_LOW_BUDGET_MAP
    elif budget_level == "medium":
        logger.info("Using MEDIUM budget LLM map.")
        return DEFAULT_MEDIUM_BUDGET_MAP
    elif budget_level == "high":
        logger.info("Using HIGH budget LLM map.")
        return DEFAULT_HIGH_BUDGET_MAP
    else:
        logger.warning(f"Invalid budget level provided: {budget_level}. Defaulting to MEDIUM.")
        return DEFAULT_MEDIUM_BUDGET_MAP