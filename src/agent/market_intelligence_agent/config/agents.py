from typing import Literal

# Define available LLM types
LLMType = Literal["basic", "reasoning", "economic", "coding"]

# Define agent-LLM mapping
AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "basic",  
    "planner": "basic",  
    "supervisor": "basic",  
    "researcher": "basic",  
    "coder": "coding",   
    "reporter": "basic",
}
