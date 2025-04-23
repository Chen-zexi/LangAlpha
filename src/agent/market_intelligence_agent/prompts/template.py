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
        research_results = state.get("research_results", [])
        if research_results:
            recent_results = research_results[-3:]
            results_text = "\n\n".join([
                f"Previous Research Task: {r['task']}\nResults: {r['output']}"
                for r in recent_results
            ])
            prompt.append({"role": "user", "content": f"Previous research context:\n{results_text}"})
            
        return prompt
        
    elif prompt_name == "coder":
        prompt = [{"role": "system", "content": system_prompt}] + [state["messages"][-1].content]
        logger.debug(f"Coder prompt: {prompt}")
        coder_results = state.get("coder_results", [])
        if coder_results:
            recent_results = coder_results[-3:]
            results_text = "\n\n".join([
                f"Previous Coding Task: {r['task']}\nCode Output: {r['output']}"
                for r in recent_results
            ])
            prompt.append({"role": "user", "content": f"Previous coding context:\n{results_text}"})
            
        return prompt
        
    else:
        return [{"role": "system", "content": system_prompt}] + state["messages"]
