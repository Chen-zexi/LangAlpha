from typing import Literal, Optional, List, Dict, Any
from pydantic import Field, BaseModel
from typing_extensions import TypedDict
from langgraph.graph import MessagesState
from datetime import datetime

from ..config import TEAM_MEMBERS

# --- Start: Model Configuration Structure ---
class ModelConfig(BaseModel):
    model: str
    provider: str
    # Add any other LLM params you might want to configure later, e.g., temperature
    # temperature: Optional[float] = None 

class LLMConfigs(BaseModel):
    reasoning: ModelConfig
    basic: ModelConfig
    coding: ModelConfig
    economic: ModelConfig
# --- End: Model Configuration Structure ---

# Define routing options
OPTIONS = TEAM_MEMBERS + ["FINISH"]


class Step(BaseModel):
    task: str
    agent: str
    description: str
    note: str | None = None

class Plan(BaseModel):
    thought: str
    title: str = Field(description="The title of the report")
    steps: List[Step]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""
    next: Literal[*OPTIONS]

class SupervisorInstructions(BaseModel):
    task: str = Field(description="The task to be performed by the agent")
    focus: str | None = Field(description="The focus of the report")
    context: str | None = Field(description="The context that the agent should consider (i.e data from another agent)")
    next: Router

class TickerInfo(BaseModel):
    company: str | None = Field(description="The name of the company")
    ticker: str | None = Field(description="The ticker symbol of the stock/company/market/sector")
    exchange: str | None = Field(description="The market/exchange that the ticker is traded on (e.g., NASDAQ, NYSE, AMEX)")
    tradingview_symbol: str | None = Field(description="The formatted symbol for TradingView widget in 'EXCHANGE:SYMBOL' format")

class CoordinatorInstructions(BaseModel):
    handoff_to_planner: bool
    time_range: str
    tickers: list[TickerInfo] | None = Field(description="The list of tickers information")

class AgentResult(BaseModel):
    """Schema for storing agent task results"""
    result_summary: str = Field(description="Breifly summarize what did you do? Maximum 2 sentences")
    output: str = Field(description="The complete output of the task")

class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Constants
    TEAM_MEMBERS: list[str]

    # Runtime Variables
    next: str
    full_plan: str
    final_report: str
    last_agent: str | None = Field(default=None)
    current_timestamp: Optional[datetime]
    researcher_credits: int = Field(default=0)
    coder_credits: int = Field(default=0)
    browser_credits: int = Field(default=0)
    market_credits: int = Field(default=0)
    time_range: str
    tickers: list[TickerInfo] | None = Field(default=None)
    agent_llm_map: Dict[str, Any] | None = Field(default=None)
    llm_configs: Optional[LLMConfigs] = Field(default=None)
