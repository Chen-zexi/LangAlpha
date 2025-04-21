from json import tool
import logging
import json
import asyncio
from copy import deepcopy
from typing import Literal
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.graph import END
import os
import uuid
import re # Import regex module

from market_intelligence_agent.agents import get_research_agent, get_coder_agent
from market_intelligence_agent.agents.llm import get_llm_by_type
from market_intelligence_agent.config import TEAM_MEMBERS
from market_intelligence_agent.config.agents import AGENT_LLM_MAP
from market_intelligence_agent.prompts.template import apply_prompt_template
from market_intelligence_agent.tools.tavily import get_tavily_tool
from market_intelligence_agent.graph.types import State, Router, SupervisorInstructions

logger = logging.getLogger(__name__)

RESPONSE_FORMAT = "Response from {}:\n\n<response>\n{}\n</response>\n\n*Please execute the next step.*"


async def research_node_async(state: State) -> Command[Literal["supervisor"]]:
    """Async version of the researcher node."""
    logger.info("Research agent starting task")
    # Get the cached agent instance (initializes on first call)
    agent = await get_research_agent()
    
    # Invoke the agent with the current state
    result = await agent.ainvoke(state)
    
    logger.info("Research agent completed task")
    logger.debug(f"Research agent response: {result['messages'][-1].content}")
    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=RESPONSE_FORMAT.format(
                        "researcher", result["messages"][-1].content
                    ),
                    name="researcher",
                )
            ]
        },
        goto="supervisor",
    )


async def research_node(state: State) -> Command[Literal["supervisor"]]:
    """Node for the researcher agent that performs research tasks.
    LangGraph typically handles async functions directly. 
    """
    return await research_node_async(state)


async def code_node_async(state: State) -> Command[Literal["supervisor"]]:
    """Async version of the coder node."""
    logger.info("Code agent starting task")
    agent = await get_coder_agent()

    # --- Prepare input state for the agent --- 
    modified_state = deepcopy(state)
    last_message_content = modified_state["messages"][-1].content

    # Define where to save the plot (you might want a more robust way)
    output_dir = os.path.abspath("./output/plots")
    unique_filename = f"plot_{uuid.uuid4()}.png"
    target_file_path = os.path.join(output_dir, unique_filename)
    
    # Append save instruction to the last message
    save_instruction = f"\n\n**Instruction:** If generating a plot, save it to the following path: '{target_file_path}'" 
    modified_state["messages"][-1].content += save_instruction
    # --- End prepare input state ---

    logger.debug(f"Invoking coder agent with state: {modified_state}")
    result = agent.invoke(modified_state)
    logger.info("Code agent completed task")
    
    agent_response_content = result['messages'][-1].content
    logger.debug(f"Code agent raw response: {agent_response_content}")

    # --- Extract file path from response --- 
    extracted_plot_path = None
    match = re.search(r"Plot saved successfully to (.*?)(?:\n|$)", agent_response_content)
    if match:
        extracted_plot_path = match.group(1).strip()
        logger.info(f"Extracted plot path: {extracted_plot_path}")
    else:
        logger.warning("Could not extract plot path from coder response.")
    # --- End extract file path ---

    # Prepare update dictionary
    update_dict = {
        "messages": [
            HumanMessage(
                content=RESPONSE_FORMAT.format(
                    "coder", agent_response_content # Use the original response content
                ),
                name="coder",
            )
        ]
    }
    # Add the extracted path if found
    if extracted_plot_path:
        update_dict["plot_file_path"] = extracted_plot_path

    return Command(update=update_dict, goto="supervisor")


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
    return Command(goto=goto, update={"next": goto, "messages": [HumanMessage(content=json.dumps(instructions), name="supervisor")]})


def planner_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
    """Planner node that generate the full plan."""
    logger.info("Planner generating full plan")
    messages = apply_prompt_template("planner", state)
    llm = get_llm_by_type("basic")
    if state.get("deep_thinking_mode"):
        llm = get_llm_by_type("reasoning")
    if state.get("search_before_planning"):
        # Get tavily tool and use it
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
        },
        goto=goto,
    )


def coordinator_node(state: State) -> Command[Literal["planner", "__end__"]]:
    """Coordinator node that communicate with customers."""
    logger.info("Coordinator talking.")
    messages = apply_prompt_template("coordinator", state)
    response = get_llm_by_type(AGENT_LLM_MAP["coordinator"]).invoke(messages)
    logger.debug(f"Current state messages: {state['messages']}")
    logger.debug(f"reporter response: {response}")

    goto = "__end__"
    if "handoff_to_planner" in response.content:
        goto = "planner"

    return Command(
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
