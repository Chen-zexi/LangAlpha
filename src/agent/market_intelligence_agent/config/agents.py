from typing import Literal

# Define available LLM types
LLMType = Literal["basic", "reasoning", "economic", "coding"]

# Define agent-LLM mapping
"""
AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "economic",  
    "planner": "reasoning",  
    "supervisor": "basic",  
    "researcher": "basic",  
    "coder": "basic",   
    "reporter": "basic",
    "analyst": "reasoning",
    "browser": "basic",
    "market": "basic",
}
"""

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
}