import os
import re
from datetime import datetime
import asyncio

# If true async file I/O is needed later:
# import aiofiles

from langchain_core.prompts import PromptTemplate
# Use typing Dict instead of AgentState if it's just a dictionary
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

# Keep sync file reading for simplicity unless it proves to be a bottleneck
def _read_prompt_file(prompt_name: str) -> str:
    """Synchronously reads the prompt file."""
    file_path = os.path.join(os.path.dirname(__file__), f"{prompt_name}.md")
    try:
        with open(file_path, 'r') as f:
            template = f.read()
        # Escape literal braces for PromptTemplate format method
        template = template.replace("{", "{{").replace("}", "}}")
        # Replace `<<VAR>>` with `{VAR}` for PromptTemplate variables
        template = re.sub(r"<<([^>>]+)>>", r"{\1}", template)
        return template
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {file_path}")
        raise # Re-raise for clearer error handling upstream

# Make the main function async
async def apply_prompt_template(prompt_name: str, state: Dict[str, Any]) -> list:
    """Asynchronously prepares the prompt message list for an agent."""

    # Run the synchronous file read in a separate thread
    template_content = await asyncio.to_thread(_read_prompt_file, prompt_name)

    # Prepare input variables for the template
    input_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state  # Pass the whole state dictionary; PromptTemplate ignores unused variables
    }

    try:
        prompt_template = PromptTemplate(template=template_content)
        # Format the template. This is CPU-bound.
        system_prompt = prompt_template.format(**input_vars)
    except KeyError as e:
        logger.error(f"Missing key in state for prompt '{prompt_name}': {e}")
        raise ValueError(f"Missing key for prompt '{prompt_name}': {e}") from e

    # Construct the final message list based on the agent type
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if prompt_name in ["researcher", "coder", "browser", "market"]:
        # These agents seem to expect system prompt + last message content as user input
        if last_message and hasattr(last_message, 'content'):
            last_message_content = last_message.content
            # Assuming the last message content should be treated as user input
            prompt = [{"role": "system", "content": system_prompt}, {"role": "user", "content": str(last_message_content)}]
            logger.debug(f"{prompt_name.capitalize()} prompt constructed.")
            return prompt
        else:
            logger.warning(f"No last message found for {prompt_name} prompt construction. Using system prompt only.")
            return [{"role": "system", "content": system_prompt}] # System prompt only

    else:  # supervisor, planner, analyst, coordinator, reporter
        # These agents seem to expect system prompt + full message history
        history_dicts = []
        for msg in messages:
             # Convert common Langchain message types to dict format
             if hasattr(msg, 'type') and hasattr(msg, 'content'):
                 role = "user" if msg.type == "human" else "assistant" if msg.type == "ai" else msg.type
                 history_dicts.append({"role": role, "content": str(msg.content)})
             elif isinstance(msg, dict) and "role" in msg and "content" in msg:
                 history_dicts.append(msg) # Already in dict format
             else:
                 logger.warning(f"Skipping unsupported message format in history for {prompt_name}: {type(msg)}")

        return [{"role": "system", "content": system_prompt}] + history_dicts
