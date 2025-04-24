from json import tool
import logging
import json
import asyncio
from copy import deepcopy
from typing import Literal
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.graph import END

from market_intelligence_agent.agents import get_research_agent, get_coder_agent, get_market_agent, get_browser_agent
from market_intelligence_agent.agents.llm import get_llm_by_type
from market_intelligence_agent.config import TEAM_MEMBERS
from market_intelligence_agent.config.agents import AGENT_LLM_MAP
from market_intelligence_agent.prompts.template import apply_prompt_template
from market_intelligence_agent.graph.types import State, SupervisorInstructions, CoordinatorInstructions
from market_intelligence_agent.config.agents import AGENT_LLM_MAP

logger = logging.getLogger(__name__)

RESPONSE_FORMAT = "Response from {}:\n\n<response>\n{}\n</response>\n\n*Please execute the next step.*"


async def research_node_async(state: State) -> Command[Literal["supervisor"]]:
    """Async version of the researcher node."""
    logger.info("Research agent starting task")
    # Get the cached agent instance (initializes on first call)
    agent = await get_research_agent()
    
    # Invoke the agent with the current state
    result = await agent.ainvoke(state)
    structured_response = result['structured_response']
    state['researcher_credits'] -= 1
    logger.info("Research agent completed task")
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=RESPONSE_FORMAT.format(
                        "researcher", structured_response.output
                    ),
                    name="researcher",
                )
            ],
            "research_result": structured_response,
            "last_agent": "researcher",
            "researcher_credits": state['researcher_credits']
        },
        goto="supervisor",
    )
    
async def market_node_async(state: State) -> Command[Literal["supervisor"]]:
    """Async version of the market node."""
    logger.info("Market agent starting task")
    # Get the cached agent instance (initializes on first call)
    agent = await get_market_agent()
    
    # Invoke the agent with the current state
    result = await agent.ainvoke(state)
    structured_response = result['structured_response']
    state['market_credits'] -= 1
    logger.info("Market agent completed task")
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=RESPONSE_FORMAT.format(
                        "market", structured_response.output
                    ),
                    name="market",
                )
            ],
            "market_result": structured_response,
            "last_agent": "market",
            "market_credits": state['market_credits']
        },
        goto="supervisor",
    )
async def market_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the market agent that performs market tasks."""
    return await market_node_async(state)


async def research_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the researcher agent that performs research tasks.
    LangGraph typically handles async functions directly. 
    """
    return await research_node_async(state)


async def code_node_async(state: State) -> Command[Literal["supervisor"]]:
    """Async version of the coder node."""
    logger.info("Code agent starting task")
    agent = await get_coder_agent()
    logger.debug(f"Invoking coder agent with state: {state}")
    result = agent.invoke(state)
    logger.info("Code agent completed task")
    structured_response = result['structured_response']
    
    state['coder_credits'] -= 1

    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=RESPONSE_FORMAT.format(
                        "coder", structured_response.output
                    ),
                    name="coder",
                )
            ],
            "coder_result": structured_response,
            "last_agent": "coder",
            "coder_credits": state['coder_credits']
        }, 
        goto="supervisor"
    )


def code_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the coder agent that executes Python code."""
    # Create a new event loop if running in a sync context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're already in an event loop, use create_task and wait
            return loop.run_until_complete(code_node_async(state))
        else:
            # No running event loop, use run_until_complete
            return loop.run_until_complete(code_node_async(state))
    except RuntimeError:
        # No event loop, create a new one
        return asyncio.run(code_node_async(state))

async def browser_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the browser agent that performs web browsing tasks."""
    logger.info("Browser agent starting task")
    agent = await get_browser_agent()
    result = await agent.ainvoke(state)
    logger.info("Browser agent completed task")
    logger.debug(f"Browser agent response: {result['messages'][-1].content}")
    state['browser_credits'] -= 1
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=RESPONSE_FORMAT.format(
                        "browser", result["messages"][-1].content
                    ),
                    name="browser",
                )
            ],
            "browser_credits": state['browser_credits']
        },
        goto="supervisor",
    )

def supervisor_node(state: State) -> Command[Literal[*TEAM_MEMBERS, "__end__"]]:
    """Supervisor node that decides which agent should act next."""
    logger.info("Supervisor evaluating next action")
    messages = apply_prompt_template("supervisor", state)
    response = (
        get_llm_by_type(AGENT_LLM_MAP["supervisor"])
        .with_structured_output(SupervisorInstructions)
        .invoke(messages)
    )
    goto = response.next["next"]
    instructions = {}
    if response.feedback is not None:
        instructions["feedback"] = response.feedback
    if response.task is not None:
        instructions["task"] = response.task
    if response.followup is not None:
        instructions["followup"] = response.followup
    if response.focus is not None:
        instructions["focus"] = response.focus
    
    logger.debug(f"Current state messages: {state['messages']}")
    logger.debug(f"Supervisor response: {response}")
    

    if goto == "FINISH":
        goto = "__end__"
        logger.info("Workflow completed")
    else:
        logger.info(f"Supervisor delegating to: {goto}")
        logger.debug(f"Supervisor instructions: {instructions}")
    return Command( 
        update={
            "next": goto, 
            "messages": [HumanMessage(content=json.dumps(instructions), name="supervisor")],
            "last_agent": "supervisor"
        },
        goto=goto, 
    )


def planner_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
    """Planner node that generate the full plan."""
    logger.info("Planner generating full plan")
    messages = apply_prompt_template("planner", state)
    llm = get_llm_by_type(AGENT_LLM_MAP["planner"])
    tool = {"type": "web_search_preview"}
    stream = llm.stream(messages, tools=[tool])
    full_response = ""
    for chunk in stream:
        full_response += chunk.text()
    logger.debug(f"Current state messages: {state['messages']}")
    logger.debug(f"Planner response: {full_response}")

    if full_response.startswith("```json"):
        full_response = full_response.removeprefix("```json")

    if full_response.endswith("```"):
        full_response = full_response.removesuffix("```")

    goto = "supervisor"
    try:
        json.loads(full_response)
    except json.JSONDecodeError:
        logger.warning("Planner response is not a valid JSON")
        goto = "__end__"

    return Command(
        update={
            "messages": [HumanMessage(content=full_response, name="planner")],
            "full_plan": full_response,
            "last_agent": "planner"
        },
        goto=goto,
    )
    
def analyst_node(state: State) -> Command[Literal["supervisor"]]:
    """Planner node that generate the full plan."""
    
    logger.info("Analyst generating full plan")
    
    messages = apply_prompt_template("analyst", state)
    llm = get_llm_by_type(AGENT_LLM_MAP["analyst"])
    tool = {"type": "web_search_preview"}
    stream = llm.stream(messages, tools=[tool])
    full_response = ""
    for chunk in stream:
        full_response += chunk.text()
        
    logger.debug(f"Analyst has finised the task")


    return Command(
        update={
            "messages": [HumanMessage(content=full_response, name="analyst")],
            "last_agent": "analyst"
        },
        goto='supervisor',
    )


def coordinator_node(state: State) -> Command[Literal["planner", "__end__"]]:
    """Coordinator node that communicate with customers."""
    logger.info("Coordinator talking.")
    messages = apply_prompt_template("coordinator", state)
    response = get_llm_by_type(AGENT_LLM_MAP["coordinator"]).with_structured_output(CoordinatorInstructions).invoke(messages)


    goto = "__end__"
    if response.handoff_to_planner:
        goto = "planner"

    return Command(
        update={
            'last_agent': 'coordinator',
            'time_range': response.time_range
        },
        goto=goto,
    )


def reporter_node(state: State) -> Command[Literal["supervisor"]]:
    """Reporter node that write a final report."""
    logger.info("Reporter write final report")
    messages = apply_prompt_template("reporter", state)
    response = get_llm_by_type(AGENT_LLM_MAP["reporter"]).invoke(messages)
    logger.debug(f"Current state messages: {state['messages']}")
    logger.debug(f"reporter response: {response}")

    return Command(
        update={
            "final_report": response.content,
        },
        goto="__end__",
    )
