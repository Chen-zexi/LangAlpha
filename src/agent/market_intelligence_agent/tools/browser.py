import asyncio

from pydantic import BaseModel, Field
from typing import Optional, ClassVar, Type
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from browser_use import AgentHistoryList, Browser, BrowserConfig
from browser_use import Agent as BrowserAgent
from ..tools.decorators import create_logged_tool
from ..config import CHROME_INSTANCE_PATH

import os

expected_browser = None
chrome_instance_path = CHROME_INSTANCE_PATH
if chrome_instance_path:
    expected_browser = Browser(
        config=BrowserConfig(chrome_instance_path=chrome_instance_path)
    )    



class BrowserUseInput(BaseModel):
    """Input for WriteFileTool."""

    instruction: str = Field(..., description="The instruction to use browser")


class BrowserTool(BaseTool):
    name: ClassVar[str] = "browser"
    args_schema: Type[BaseModel] = BrowserUseInput
    description: ClassVar[str] = (
        "Use this tool to interact with web browsers. Input should be a natural language description of what you want to do with the browser, such as 'Go to google.com and search for browser-use', or 'Navigate to Reddit and find the top post about AI'."
    )

    _agent: Optional[BrowserAgent] = None

    def _run(self, instruction: str) -> str:
        """Run the browser task synchronously."""
        self._agent = BrowserAgent(
            task=instruction,  # Will be set per request
            llm=ChatOpenAI(model="gpt-4.1", api_key=os.getenv("OPENAI_API_KEY")),
            browser=expected_browser,
        )
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._agent.run())
                return (
                    str(result)
                    if not isinstance(result, AgentHistoryList)
                    else result.final_result
                )
            finally:
                loop.close()
        except Exception as e:
            return f"Error executing browser task: {str(e)}"

    async def _arun(self, instruction: str) -> str:
        """Run the browser task asynchronously."""
        self._agent = BrowserAgent(
            task=instruction, llm=create_basic_llm(model="gpt-4.1", provider="OPENAI")  # Will be set per request
        )
        try:
            result = await self._agent.run()
            return (
                str(result)
                if not isinstance(result, AgentHistoryList)
                else result.final_result
            )
        except Exception as e:
            return f"Error executing browser task: {str(e)}"


BrowserTool = create_logged_tool(BrowserTool)
browser_tool = BrowserTool()
