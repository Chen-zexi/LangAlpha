from mcp.server.fastmcp import FastMCP
import requests
import asyncio
import os
from typing import List, Optional, Literal
import json

# Create the MCP server with a meaningful name
mcp = FastMCP("TavilyMCP")

# Tavily API endpoint
TAVILY_API_ENDPOINT = "https://api.tavily.com/search"

# Base API client functions
async def async_tavily_search(
    query: str,
    api_key: Optional[str] = None,
    search_depth: Literal["basic", "advanced"] = "basic",
    topic: Literal["general", "news"] = "general",
    days: Optional[int] = None,
    time_range: Literal["days", "weeks", "months", "years"] = None,
    max_results: Optional[int] = None
):
    """Asynchronous function to perform Tavily search using direct API calls"""
    api_key = api_key or os.getenv("TAVILY_API_KEY", "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")
    if not api_key:
        return {"error": "Tavily API key not provided or found in environment"}
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "query": query,
        "search_depth": search_depth,
        "include_answer": True,
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "chunks_per_source": 3,
    }
    
    if topic:
        payload["topic"] = topic
    if days:
        payload["days"] = days
    if time_range:
        payload["time_range"] = time_range
    if max_results:
        payload["max_results"] = max_results
    
    try:
        # Use asyncio to run the request in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(TAVILY_API_ENDPOINT, headers=headers, json=payload)
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"API request failed with status code {response.status_code}",
                "message": response.text
            }
    except Exception as e:
        return {"error": str(e)}

# Define MCP tools
@mcp.tool()
async def search(
    query: str,
    search_depth: Literal["basic", "advanced"] = "basic",
    topic: Optional[str] = None,
    days: Optional[int] = None,
    time_range: Optional[str] = None,
    max_results: Optional[int] = None
) -> dict:
    """
    Search the web using Tavily API.
    
    Args:
        query: The search query
        search_depth: Depth of search, 'basic' or 'advanced'
        topic: Filter results by by either "general" or "news", you should always use "general" unless you are compiled to search for news
        days: Number of days to look back for results
        time_range: Time range for results, accepts "day", "week", "month", "year"
        max_results: Maximum number of results to return
    
    Returns:
        A dictionary containing search results
    """
    return await async_tavily_search(
        query=query,
        search_depth=search_depth,
        topic=topic,
        days=days,
        time_range=time_range,
        max_results=max_results
    )


# Add this to run the server with stdio transport when executed directly
if __name__ == "__main__":
    mcp.run(transport="stdio") 