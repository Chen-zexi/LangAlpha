import logging
from typing import Annotated
from langchain_core.tools import tool
from .decorators import log_io
import os

import re
from daytona_sdk import Daytona, DaytonaConfig, CreateSandboxParams, SandboxResources
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('DAYTONA_API_KEY')
if not api_key:
    raise "no api key"
config = DaytonaConfig(api_key=api_key)
daytona = Daytona(config)



resources = SandboxResources(
    cpu=2,      # 2 CPU cores
    memory=4,   # 4GB RAM
    disk=10,    # 20GB disk space
)

params = CreateSandboxParams(
    language="python",
    resources=resources
)

#sandbox = daytona.create(params)

logger = logging.getLogger(__name__)
@tool
@log_io
def python_code_tool(
    code: Annotated[
        str, "only the code. No explanation. No intro. No comments. Just raw code in a single code block."
    ],
):
    """Executes python code and returns the result. The code runs in a static sandbox without interactive mode, so make sure to print output only."""
    logger.info("Executing Python code")

    try:
        code_match = re.search(r"```python\n(.*?)```", code, re.DOTALL)
        code = code_match.group(1) if code_match else code
        code = code.replace('\\', '\\\\')
        result = sandbox.process.code_run(code)
        logger.info("Code execution successful")
    except BaseException as e:
        error_msg = f"Failed to execute. Error: {repr(e)}"
        logger.error(error_msg)
        return error_msg
    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
    return result_str


@tool
@log_io
def bash_tool(
    cmd: Annotated[str, "The bash command to be executed."],
):
    """Executes bash command and returns the result. always use this tool to download the packge you need first before excuting python code"""
    logger.info("Executing bash cmd")

    try:
        cmd_match = re.search(r"```bash\n(.*?)```", cmd, re.DOTALL)
        cmd = cmd_match.group(1) if cmd_match else cmd
        cmd = cmd.replace('\\', '\\\\')
        result = sandbox.process.exec(cmd)
        logger.info("Code execution successful")
    except BaseException as e:
        error_msg = f"Failed to execute. Error: {repr(e)}"
        logger.error(error_msg)
        return error_msg
    result_str = f"Successfully executed:\n```bash\n{cmd}\n```\nStdout: {result}"
    return result_str