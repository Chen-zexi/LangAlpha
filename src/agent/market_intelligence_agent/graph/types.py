from typing import Literal, Optional
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
    
class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Constants
    TEAM_MEMBERS: list[str]

    # Runtime Variables
    next: str
    full_plan: str
    final_report: str
    deep_thinking_mode: bool
    search_before_planning: bool
    plot_file_path: Optional[str]
    current_timestamp: Optional[datetime]
