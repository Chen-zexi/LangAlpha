import logging
import json
import asyncio
from typing import Literal, List, Any, Dict
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from langgraph.graph import END
from langgraph.prebuilt import create_react_agent

from ..agents import get_coder_agent, get_browser_agent
from ..agents.llm import get_llm_by_type
from ..config import TEAM_MEMBERS
from ..config.agents import AGENT_LLM_MAP
from ..prompts.template import apply_prompt_template
from .types import State, SupervisorInstructions, CoordinatorInstructions, Plan, AgentResult
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

RESPONSE_FORMAT = "Response from {}:\n\n<response>\n{}\n</response>\n\n*Please execute the next step.*"

source_dir = Path(__file__).parent.parent

async def research_node(state: State) -> Command[Literal["supervisor"]]:
    """Research node that performs research tasks with proper resource management."""
    prompt_messages = await apply_prompt_template("researcher", state)
    async with MultiServerMCPClient(
        {
            "tavily_search": {
                "command": "python",
                "args": [str(source_dir / "tools" / "tavily.py")],
                "transport": "stdio",
            },
            "tickertick": {
                "command": "python",
                "args": [str(source_dir / "tools" / "tickertick.py")],
                "transport": "stdio",
            }
        }
    ) as client:
        tools = client.get_tools()
        agent = create_react_agent(
            get_llm_by_type(AGENT_LLM_MAP["researcher"]),
            tools=tools,
            response_format=AgentResult
        )
        input_data = {**state, "messages": prompt_messages}
        result = await agent.ainvoke(input_data)
        
        structured_response = result.get('structured_response')
        
        if structured_response:
            response_dump = structured_response.model_dump()
        else:
            logger.warning("Researcher agent did not return a structured_response.")
            raw_content = result.get('messages', [AIMessage(content="Error: No structured response.")])[-1].content
            response_dump = {"error": "No structured response", "raw_content": raw_content}

        state['researcher_credits'] -= 1
        goto = "supervisor"

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=json.dumps(response_dump),
                        name="researcher",
                    )
                ],
                "last_agent": "researcher",
                "researcher_credits": state['researcher_credits'],
                "next": goto
            },
            goto=goto,
        )
    
async def market_node(state: State) -> Command[Literal["supervisor"]]:
    """Market node that performs market analysis tasks with proper resource management."""
    prompt_messages = await apply_prompt_template("market", state)
    async with MultiServerMCPClient(
        {
            "market_data": {
                "command": "python",
                "args": [str(source_dir / "tools" / "market_data.py")],
                "transport": "stdio",
            },
            "fundamental_data": {
                "command": "python",
                "args": [str(source_dir / "tools" / "fundamental_data.py")],
                "transport": "stdio",
            }
        }
    ) as client:
        tools = client.get_tools()
        agent = create_react_agent(
            get_llm_by_type(AGENT_LLM_MAP["market"]),
            tools=tools,
            response_format=AgentResult
        )
        input_data = {**state, "messages": prompt_messages}
        result = await agent.ainvoke(input_data)
        
        structured_response = result.get('structured_response')
        if structured_response:
            response_dump = structured_response.model_dump()
        else:
            logger.warning("Market agent did not return a structured_response.")
            raw_content = result.get('messages', [AIMessage(content="Error: No structured response.")])[-1].content
            response_dump = {"error": "No structured response", "raw_content": raw_content}

        state['market_credits'] -= 1
        goto = "supervisor"

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=json.dumps(response_dump),
                        name="market",
                    )
                ],
                "last_agent": "market",
                "market_credits": state['market_credits'],
                "next": goto
            },
            goto=goto,
        )


async def code_node_async(state: State) -> Command[Literal["supervisor"]]:
    """Async Code node that executes Python code."""
    agent = await get_coder_agent()

    prompt_messages = await apply_prompt_template("coder", state)
    input_data = {**state, "messages": prompt_messages}

    result = await agent.ainvoke(input_data)

    structured_response = result.get('structured_response')
    if structured_response:
         if hasattr(structured_response, 'model_dump'):
             response_dump = structured_response.model_dump()
         elif isinstance(structured_response, dict):
             response_dump = structured_response
         else:
             logger.warning("Coder agent structured_response is not a Pydantic model or dict.")
             response_dump = {"raw_content": str(structured_response)}
    else:
        logger.warning("Coder agent did not return a structured_response.")
        raw_content = result.get('messages', [AIMessage(content="Error: No structured response.")])[-1].content
        response_dump = {"error": "No structured response", "raw_content": raw_content}

    goto = "supervisor"
    state['coder_credits'] -= 1

    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=json.dumps(response_dump),
                    name="coder",
                )
            ],
            "last_agent": "coder",
            "coder_credits": state['coder_credits'],
            "next": goto
        },
        goto=goto
    )


def code_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the coder agent that executes Python code."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return loop.run_until_complete(code_node_async(state))
        else:
            return loop.run_until_complete(code_node_async(state))
    except RuntimeError:
        return asyncio.run(code_node_async(state))

async def browser_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the browser agent that performs web browsing tasks."""
    agent = await get_browser_agent()

    prompt_messages = await apply_prompt_template("browser", state)
    input_data = {**state, "messages": prompt_messages}

    result = await agent.ainvoke(input_data)

    state['browser_credits'] -= 1
    goto = "supervisor"

    final_content = "Error: No message content found."
    if result and "messages" in result and result["messages"]:
        last_msg = result["messages"][-1]
        if hasattr(last_msg, 'content'):
            final_content = last_msg.content
        elif isinstance(last_msg, str):
             final_content = last_msg

    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=RESPONSE_FORMAT.format(
                        "browser", final_content
                    ),
                    name="browser",
                )
            ],
            "browser_credits": state['browser_credits'],
            "next": goto
        },
        goto=goto,
    )

async def supervisor_node(state: State) -> Command[Literal[*TEAM_MEMBERS, "__end__"]]:
    """Supervisor node that decides which agent should act next."""
    messages = await apply_prompt_template("supervisor", state)
    llm = (
        get_llm_by_type(AGENT_LLM_MAP["supervisor"])
        .with_structured_output(SupervisorInstructions)
    )
    response = await llm.ainvoke(messages)

    goto = response.next["next"]
    instructions = {}
    if response.task is not None:
        instructions["task"] = response.task
    if response.focus is not None:
        instructions["focus"] = response.focus
    if response.context is not None:
        instructions["context"] = response.context

    if goto == "FINISH":
        goto = "__end__"
    
    return Command( 
        update={
            "next": goto, 
            "messages": [HumanMessage(content=json.dumps(instructions), name="supervisor")],
            "last_agent": "supervisor"
        },
        goto=goto, 
    )


async def planner_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
    """Planner node that generates the full plan."""
    messages = await apply_prompt_template("planner", state)
    llm = get_llm_by_type(AGENT_LLM_MAP["planner"]).with_structured_output(Plan)
    tool = {"type": "web_search_preview"}
    full_plan_obj = await llm.ainvoke(messages, tools=[tool])

    goto = "supervisor"
    full_plan_json = ""
    try:
        if hasattr(full_plan_obj, 'model_dump_json'):
            full_plan_json = full_plan_obj.model_dump_json()
        else:
             full_plan_json = json.dumps(full_plan_obj)
             logger.warning("Planner response object does not have model_dump_json. Using standard json.dumps.")
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Planner response could not be serialized to JSON: {e}")
        full_plan_json = json.dumps({"error": "Failed to serialize plan", "details": str(e)})

    return Command(
        update={
            "next": goto,
            "messages": [HumanMessage(content=full_plan_json, name="planner")],
            "full_plan": full_plan_json,
            "last_agent": "planner"
        },
        goto=goto,
    )
    
async def analyst_node(state: State, response_api = True) -> Command[Literal["supervisor"]]:
    """Analyst node that generates analysis."""
    messages = await apply_prompt_template("analyst", state)
    llm = get_llm_by_type(AGENT_LLM_MAP["analyst"])
    logger.info(f"Analyst result: {result}")
    if response_api:
        tool = {"type": "web_search_preview"}
        result = await llm.ainvoke(messages, tools=[tool])
        result = result.text()
    else:
        result = await llm.ainvoke(messages)

    goto = "supervisor"

    return Command(
        update={
            "next": goto,
            "messages": [HumanMessage(content=result, name="analyst")],
            "last_agent": "analyst"
        },
        goto=goto,
    )


async def coordinator_node(state: State) -> Command[Literal["planner", "__end__"]]:
    """Coordinator node that communicates with customers."""
    logger.info(f"Budget for LLM: {AGENT_LLM_MAP.get('budget', 'Not Set')}")
    messages = await apply_prompt_template("coordinator", state)
    llm = get_llm_by_type(AGENT_LLM_MAP["coordinator"]).with_structured_output(CoordinatorInstructions)
    response = await llm.ainvoke(messages)
    goto = "__end__"
    if response.handoff_to_planner:
        goto = "planner"

    time_range = response.time_range if hasattr(response, 'time_range') else None

    return Command(
        update={
            'last_agent': 'coordinator',
            'time_range': time_range,
            'next': goto
        },
        goto=goto,
    )


async def reporter_node(state: State) -> Command[Literal["__end__"]]:
    """Reporter node that writes a final report."""
    messages = await apply_prompt_template("reporter", state)
    llm = get_llm_by_type(AGENT_LLM_MAP["reporter"])
    response = await llm.ainvoke(messages)

    final_report_content = response.content if hasattr(response, 'content') else str(response)

    return Command(
        update={
            "messages": [AIMessage(content="Reporter has finished the task.", name="reporter")],
            "final_report": final_report_content,
        },
        goto="__end__",
    )
