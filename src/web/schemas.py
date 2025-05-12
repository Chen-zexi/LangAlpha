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

# New Schemas for Ginzu Analysis API
class GinzuAnalysisRequest(BaseModel):
    ticker: str
    country: str
    us_industry: str
    global_industry: str
    # Values are expected as percentages, e.g., 5.0 for 5%
    revenue_growth_rate_next_year: Optional[float] = None 
    operating_margin_next_year: Optional[float] = None
    cagr_5yr_revenue: Optional[float] = None
    target_pre_tax_operating_margin: Optional[float] = None
    years_to_converge_margin: Optional[float] = None
    sales_to_capital_ratio_yrs_1_5: Optional[float] = None
    sales_to_capital_ratio_yrs_6_10: Optional[float] = None

class GinzuAnalysisResponse(BaseModel):
    message: Optional[str] = None
    estimated_value_per_share: Optional[float] = None
    price: Optional[float] = None
    price_as_percentage_of_value: Any
    error: Optional[str] = None 