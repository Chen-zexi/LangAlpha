import logging
import json
import asyncio
import os
from typing import Literal, List, Any, Dict, Optional
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from langgraph.graph import END
from langgraph.prebuilt import create_react_agent

from ..agents import get_coder_agent, get_browser_agent
from ..agents.llm import get_llm_by_type
from ..config import TEAM_MEMBERS
from ..config.agents import get_agent_llm_map
from ..prompts.template import apply_prompt_template
from .types import State, SupervisorInstructions, CoordinatorInstructions, Plan, AgentResult, LLMConfigs
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

RESPONSE_FORMAT = "Response from {}:\n\n<response>\n{}\n</response>\n\n*Please execute the next step.*"

source_dir = Path(__file__).parent.parent

# Helper function to get the agent LLM map from state with a fallback
def _get_map_from_state(state: State) -> Dict[str, Any]:
    agent_llm_map = state.get('agent_llm_map')
    if not agent_llm_map:
        logger.warning("agent_llm_map not found in state. Using default MEDIUM budget map.")
        return get_agent_llm_map("medium") 
    return agent_llm_map

# Helper function to get the LLM configs from state
def _get_llm_configs_from_state(state: State) -> Optional[Dict[str, Any]]:
    llm_configs_obj = state.get('llm_configs')
    if isinstance(llm_configs_obj, LLMConfigs): # If it's the Pydantic model
        return llm_configs_obj.model_dump()
    elif isinstance(llm_configs_obj, dict): # If it's already a dict
        return llm_configs_obj
    else:
        logger.info(f"type: {type(llm_configs_obj)}")
        logger.info(f"llm_configs: {llm_configs_obj}")
        logger.warning("llm_configs not found or invalid in state. LLM creation will use defaults.")
        return None

async def research_node(state: State) -> Command[Literal["supervisor"]]:
    """Research node that performs research tasks with proper resource management."""
    agent_llm_map = _get_map_from_state(state)
    llm_configs = _get_llm_configs_from_state(state) # Get LLM configs
    researcher_llm_type = agent_llm_map.get("researcher", "economic") # Determine type
    logger.info(f"Using researcher LLM type: {researcher_llm_type}")
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
        researcher_llm = get_llm_by_type(researcher_llm_type, llm_configs) # Pass configs
        agent = create_react_agent(
            researcher_llm, 
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

        # Ensure researcher_credits key exists before decrementing
        current_credits = state.get('researcher_credits', 0)
        state['researcher_credits'] = max(0, current_credits - 1)
        
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
    agent_llm_map = _get_map_from_state(state)
    llm_configs = _get_llm_configs_from_state(state) # Get LLM configs
    market_llm_type = agent_llm_map.get("market", "economic") # Determine type
    logger.info(f"Using market LLM type: {market_llm_type}")
    prompt_messages = await apply_prompt_template("market", state)
    
    polygon_api_key = os.getenv('POLYGON_API_KEY')
    alpha_vantage_api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    financialmodelingprep_api_key = os.getenv('FINANCIALMODELINGPREP_API_KEY')
    async with MultiServerMCPClient(
        {
            "market_data": {
                "command": "python",
                "args": [str(source_dir / "tools" / "market_data.py")],
                "transport": "stdio",
                "env": {"POLYGON_API_KEY": polygon_api_key}
            },
            "fundamental_data": {
                "command": "python",
                "args": [str(source_dir / "tools" / "fundamental_data.py")],
                "transport": "stdio",
                "env": {"ALPHA_VANTAGE_API_KEY": alpha_vantage_api_key}
            },
            "fundamental_data_fmp": {
                "command": "python",
                "args": [str(source_dir / "tools" / "fundamental_data_fmp.py")],
                "transport": "stdio",
                "env": {"FINANCIALMODELINGPREP_API_KEY": financialmodelingprep_api_key}
            }
        }
    ) as client:
        tools = client.get_tools()
        market_llm = get_llm_by_type(market_llm_type, llm_configs) # Pass configs
        agent = create_react_agent(
            market_llm,
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

        # Ensure market_credits key exists before decrementing
        current_credits = state.get('market_credits', 0)
        state['market_credits'] = max(0, current_credits - 1)

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


async def coder_node(state: State) -> Command[Literal["supervisor"]]:
    """Async Code node that executes Python code."""
    agent_llm_map = _get_map_from_state(state) 
    coder_llm_type = agent_llm_map.get("coder", "coding") 
    logger.info(f"Using coder LLM type: {coder_llm_type}")
    llm_configs = _get_llm_configs_from_state(state)
    agent = await get_coder_agent(llm_type=coder_llm_type, llm_configs=llm_configs) # Hypothetical modification

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
    # Ensure coder_credits key exists before decrementing
    current_credits = state.get('coder_credits', 0)
    state['coder_credits'] = max(0, current_credits - 1)

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



async def browser_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the browser agent that performs web browsing tasks."""
    agent_llm_map = _get_map_from_state(state)
    browser_llm_type = agent_llm_map.get("browser", "economic") 
    logger.info(f"Using browser LLM type: {browser_llm_type}")
    # Similar challenge as coder_node
    # Assuming get_browser_agent is modified to accept llm_configs
    llm_configs = _get_llm_configs_from_state(state)
    agent = await get_browser_agent(llm_type=browser_llm_type, llm_configs=llm_configs) # Hypothetical modification

    prompt_messages = await apply_prompt_template("browser", state)
    input_data = {**state, "messages": prompt_messages}

    result = await agent.ainvoke(input_data)

    # Ensure browser_credits key exists before decrementing
    current_credits = state.get('browser_credits', 0)
    state['browser_credits'] = max(0, current_credits - 1)
    
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
    agent_llm_map = _get_map_from_state(state)
    llm_configs = _get_llm_configs_from_state(state) # Get LLM configs
    supervisor_llm_type = agent_llm_map.get("supervisor", "basic") # Determine type
    
    messages = await apply_prompt_template("supervisor", state)
    supervisor_llm = get_llm_by_type(supervisor_llm_type, llm_configs) # Pass configs
    llm = supervisor_llm.with_structured_output(SupervisorInstructions)
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


async def planner_node(state: State, use_web_search: bool = False) -> Command[Literal["supervisor", "__end__"]]:
    """Planner node that generates the full plan."""
    agent_llm_map = _get_map_from_state(state)
    llm_configs = _get_llm_configs_from_state(state) # Get LLM configs
    planner_llm_type = agent_llm_map.get("planner", "basic") # Determine type
    
    messages = await apply_prompt_template("planner", state)
    planner_llm = get_llm_by_type(planner_llm_type, llm_configs) # Pass configs
    llm = planner_llm.with_structured_output(Plan)
    if use_web_search:
        tool = {"type": "web_search_preview"}
        full_plan_obj = await llm.ainvoke(messages, tools=[tool])
    else:
        full_plan_obj = await llm.ainvoke(messages)

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
    
async def analyst_node(state: State, use_web_search: bool = False) -> Command[Literal["supervisor"]]:
    """Analyst node that generates analysis."""
    agent_llm_map = _get_map_from_state(state)
    llm_configs = _get_llm_configs_from_state(state) # Get LLM configs
    analyst_llm_type = agent_llm_map.get("analyst", "basic") # Determine type
    
    messages = await apply_prompt_template("analyst", state)
    analyst_llm = get_llm_by_type(analyst_llm_type, llm_configs) # Pass configs
    if use_web_search:
        tool = {"type": "web_search_preview"}
        result = await analyst_llm.ainvoke(messages, tools=[tool])
        result = result.text()
    else:
        result_obj = await analyst_llm.ainvoke(messages)
        result = result_obj.content if hasattr(result_obj, 'content') else str(result_obj)

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
    agent_llm_map = _get_map_from_state(state)
    llm_configs = _get_llm_configs_from_state(state) # Get LLM configs
    coordinator_llm_type = agent_llm_map.get("coordinator", "basic") # Determine type
    
    logger.info(f"Budget for LLM: {agent_llm_map.get('budget', 'Not Set')}")
    messages = await apply_prompt_template("coordinator", state)
    coordinator_llm = get_llm_by_type(coordinator_llm_type, llm_configs) # Pass configs
    llm = coordinator_llm.with_structured_output(CoordinatorInstructions) 
    response = await llm.ainvoke(messages)
    goto = "__end__"
    if response.handoff_to_planner:
        goto = "planner"

    time_range = response.time_range if hasattr(response, 'time_range') else None
    ticker_type = response.ticker_type if hasattr(response, 'ticker_type') else None
    tickers = response.tickers if hasattr(response, 'tickers') else None
    return Command(
        update={
            'last_agent': 'coordinator',
            'time_range': time_range,
            'ticker_type': ticker_type,
            'tickers': tickers,
            'next': goto
        },
        goto=goto,
    )


async def reporter_node(state: State) -> Command[Literal["__end__"]]:
    """Reporter node that writes a final report."""
    agent_llm_map = _get_map_from_state(state)
    llm_configs = _get_llm_configs_from_state(state) # Get LLM configs
    reporter_llm_type = agent_llm_map.get("reporter", "basic") # Determine type
    
    messages = await apply_prompt_template("reporter", state)
    reporter_llm = get_llm_by_type(reporter_llm_type, llm_configs) # Pass configs
    response = await reporter_llm.ainvoke(messages)

    final_report_content = response.content if hasattr(response, 'content') else str(response)

    return Command(
        update={
            "messages": [AIMessage(content="Reporter has finished the task.", name="reporter")],
            "final_report": final_report_content,
        },
        goto="__end__",
    )
