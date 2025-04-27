import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import List, Any, Dict, Callable

# Configuration for the MCP servers
MCP_SERVERS_MARKET = {
    "market_data": {
        "command": "python",
        "args": ["/Users/chen/Library/Mobile Documents/com~apple~CloudDocs/NYU/SPRING 25/TECH-UB 24/LangAlpha/src/mcp_server/market_data.py"],
        "transport": "stdio",
    },
    "fundamental_data": {
        "command": "python",
        "args": ["/Users/chen/Library/Mobile Documents/com~apple~CloudDocs/NYU/SPRING 25/TECH-UB 24/LangAlpha/src/mcp_server/fundamental_data.py"],
        "transport": "stdio",
    }
}

async def execute_with_market_tools(operation: Callable[[List[Any], Dict[str, Any]], Any], state: Dict[str, Any]):
    """
    Creates a new MCP client, connects to market servers, performs the operation, 
    and ensures proper cleanup within the same task.
    
    Args:
        operation: A callable that takes (tools, state) and returns a result
        state: The state dictionary to pass to the operation
        
    Returns:
        The result of the operation
    """
    # Create a new client for this specific operation
    client = MultiServerMCPClient()
    
    # Setup phase
    try:
        # Start the client
        await client.__aenter__()
        
        # Connect to all servers
        connect_tasks = []
        for name, params in MCP_SERVERS_MARKET.items():
            connect_tasks.append(client.connect_to_server(name, **params))
        
        await asyncio.gather(*connect_tasks)
        
        # Get tools
        tools = client.get_tools()
        
        # Perform the operation
        result = await operation(tools, state)
        
        return result
    
    finally:
        # Always clean up
        try:
            await client.__aexit__(None, None, None)
        except Exception as e:
            print(f"Warning: Error during market client cleanup: {e}")
            # Continue execution even if cleanup fails

