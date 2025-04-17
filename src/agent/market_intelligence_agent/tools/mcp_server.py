import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

class MCPConnectionManager:
    def __init__(self):
        self.client = None

    async def connect(self):
        self.client = MultiServerMCPClient()
        await self.client.__aenter__()
        await self.client.connect_to_server(
            "tavily_search",
            command="python",
            args=["/Users/chen/Library/Mobile Documents/com~apple~CloudDocs/NYU/SPRING 25/TECH-UB 24/StocksFlags/src/mcp_server/tavily.py"],
            transport="stdio",
        )
        await self.client.connect_to_server(
            "tickertick",
            command="python",
            args=["/Users/chen/Library/Mobile Documents/com~apple~CloudDocs/NYU/SPRING 25/TECH-UB 24/StocksFlags/src/mcp_server/tickertick.py"],
            transport="stdio",
        )

    async def get_tools(self):
        return self.client.get_tools()

    async def close(self):
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.client = None

# Create a global connection manager
_global_connection_manager = None

async def mcp_connection_manager():
    """Returns the MCPConnectionManager instance."""
    connection_manager = MCPConnectionManager()
    await connection_manager.connect()
    return connection_manager  # Return the instance, don't close here!

async def get_global_mcp_connection():
    """Returns a global singleton MCPConnectionManager instance."""
    global _global_connection_manager
    if _global_connection_manager is None:
        _global_connection_manager = MCPConnectionManager()
        await _global_connection_manager.connect()
    return _global_connection_manager