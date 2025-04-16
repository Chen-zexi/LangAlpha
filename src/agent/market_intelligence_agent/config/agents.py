from typing import Literal

# Define available LLM types
LLMType = Literal["basic", "reasoning"]

# Define agent-LLM mapping
AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "basic",  
    "planner": "reasoning",  
    "supervisor": "basic",  
    "researcher": "basic",  
    "coder": "basic",   
    "reporter": "basic",
}
