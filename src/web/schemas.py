from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime 
class WorkflowRequest(BaseModel):
    query: str

class StreamConfig(BaseModel):
    recursion_limit: int = 150

class ModelConfig(BaseModel):
    model: str
    provider: str

class LLMConfigs(BaseModel):
    reasoning: ModelConfig
    basic: ModelConfig
    coding: ModelConfig
    economic: ModelConfig

class WorkflowConfig(BaseModel):
    team_members: Optional[Dict[str, Any]] = None
    researcher_credits: int = 6
    market_credits: int = 6
    coder_credits: int = 0
    browser_credits: int = 3
    stream_config: Optional[StreamConfig] = Field(default_factory=StreamConfig)
    budget: Optional[Literal["low", "medium", "high"]] = "low"
    llm_configs: Optional[LLMConfigs] = None 