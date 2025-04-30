from typing import Literal
from .env import BUDGET
import logging

logger = logging.getLogger(__name__)

# Define available LLM types
LLMType = Literal["basic", "reasoning", "economic", "coding"]

if BUDGET == "low":
    AGENT_LLM_MAP: dict[str, LLMType] = {
        "coordinator": "economic",  
        "planner": "economic",  
        "supervisor": "economic",  
        "researcher": "economic",  
        "coder": "economic",   
        "reporter": "economic",
        "analyst": "economic",
        "browser": "economic",
        "market": "economic",
        "budget": BUDGET,
    }
    
elif BUDGET == "medium":
    AGENT_LLM_MAP: dict[str, LLMType] = {
        "coordinator": "basic",  
        "planner": "basic",  
        "supervisor": "basic",  
        "researcher": "basic",  
        "coder": "basic",   
        "reporter": "basic",
        "analyst": "basic",
        "browser": "basic",
        "market": "basic",
        "budget": BUDGET,
    }
elif BUDGET == "high":
    AGENT_LLM_MAP: dict[str, LLMType] = {
        "coordinator": "basic",  
        "planner": "reasoning",  
        "supervisor": "basic",  
        "researcher": "basic",
        "coder": "coding",
        "reporter": "basic",
        "analyst": "basic",
        "browser": "basic",
        "market": "basic",
        "budget": BUDGET,
    }
else:
    logger.warning(f"Invalid budget: {BUDGET}. Defaulting to 'medium'.")
    AGENT_LLM_MAP: dict[str, LLMType] = {
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