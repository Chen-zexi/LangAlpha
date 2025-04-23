from typing import Literal, Optional, List
from pydantic import Field, BaseModel
from typing_extensions import TypedDict
from langgraph.graph import MessagesState
from datetime import datetime

from market_intelligence_agent.config import TEAM_MEMBERS

# Define routing options
OPTIONS = TEAM_MEMBERS + ["FINISH"]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""
    next: Literal[*OPTIONS]

class SupervisorInstructions(BaseModel):
    task: str | None = Field(description="The task to be performed by the agent")
    followup: str | None = Field(description="Follow up question to the user")
    focus: str | None = Field(description="The focus of the report")
    feedback: str | None = Field(description="Feedback and instruction to the agent")
    next: Router
    
class CoordinatorInstructions(BaseModel):
    handoff_to_planner: bool
    time_range: str

class AgentResult(BaseModel):
    """Schema for storing agent task results"""
    task: str = Field(description="The task that was performed")
    output: str = Field(description="The output of the task")

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
    research_results: List[AgentResult] = Field(default_factory=list)
    coder_results: List[AgentResult] = Field(default_factory=list)
    time_range: str
