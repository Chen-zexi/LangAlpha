import os
import re
from datetime import datetime

from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt.chat_agent_executor import AgentState
import logging

logger = logging.getLogger(__name__)

def get_prompt_template(prompt_name: str) -> str:
    template = open(os.path.join(os.path.dirname(__file__), f"{prompt_name}.md")).read()
    # Escape curly braces using backslash
    template = template.replace("{", "{{").replace("}", "}}")
    # Replace `<<VAR>>` with `{VAR}`
    template = re.sub(r"<<([^>>]+)>>", r"{\1}", template)
    return template


def apply_prompt_template(prompt_name: str, state: AgentState) -> list:
    
    system_prompt = PromptTemplate(
        input_variables=["CURRENT_TIME"],
        template=get_prompt_template(prompt_name),
    ).format(CURRENT_TIME=datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"), **state)
    
    if prompt_name == "researcher":
        prompt = [{"role": "system", "content": system_prompt}] + [state["messages"][-1].content]
        logger.debug(f"Researcher prompt: {prompt}")           
        return prompt
        
    elif prompt_name == "coder":
        prompt = [{"role": "system", "content": system_prompt}] + [state["messages"][-1].content]
        logger.debug(f"Coder prompt: {prompt}")            
        return prompt
    
    elif prompt_name == "browser":
        prompt = [{"role": "system", "content": system_prompt}] + [state["messages"][-1].content]
        return prompt

    
    elif prompt_name == "market":
        prompt = [{"role": "system", "content": system_prompt}] + [state["messages"][-1].content]
        return prompt
        
    else:
        return [{"role": "system", "content": system_prompt}] + state["messages"]
