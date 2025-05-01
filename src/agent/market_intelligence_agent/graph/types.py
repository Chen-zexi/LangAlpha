from typing import Literal, Optional, List
from pydantic import Field, BaseModel
from typing_extensions import TypedDict
from langgraph.graph import MessagesState
from datetime import datetime

from ..config import TEAM_MEMBERS

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
    
class CoordinatorInstructions(BaseModel):
    handoff_to_planner: bool
    time_range: str

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
