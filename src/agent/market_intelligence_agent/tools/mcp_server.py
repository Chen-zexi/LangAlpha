import asyncio
from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import List, Any

# Configuration for the MCP servers
# It's better to manage file paths potentially through config or environment variables
# but using the existing hardcoded paths for now.
MCP_SERVERS = {
    "tavily_search": {
        "command": "python",
        "args": ["/Users/chen/Library/Mobile Documents/com~apple~CloudDocs/NYU/SPRING 25/TECH-UB 24/LangAlpha/src/mcp_server/tavily.py"],
        "transport": "stdio",
    },
    "tickertick": {
        "command": "python",
        "args": ["/Users/chen/Library/Mobile Documents/com~apple~CloudDocs/NYU/SPRING 25/TECH-UB 24/LangAlpha/src/mcp_server/tickertick.py"],
        "transport": "stdio",
    }
}

@asynccontextmanager
async def managed_mcp_tools() -> List[Any]:
    """
    An async context manager that connects to MCP servers,
    yields the combined tools, and ensures cleanup.
    """
    client = MultiServerMCPClient()
    try:
        # Enter the client's context (starts background tasks if any)
        await client.__aenter__()

        # Connect to all configured servers
        connect_tasks = [
            client.connect_to_server(name, **params)
            for name, params in MCP_SERVERS.items()
        ]
        await asyncio.gather(*connect_tasks)

        # Yield the tools for use within the 'async with' block
        yield client.get_tools()

    finally:
        # Exit the client's context (cleans up connections, stops servers)
        # The __aexit__ handles potential exceptions during cleanup internally
        await client.__aexit__(None, None, None)

