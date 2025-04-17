from langchain_community.tools.tavily_search import TavilySearchResults
import os
from typing import Dict, Any, Union

# Singleton pattern to avoid multiple instantiations
_tavily_tool = None

def get_tavily_tool():
    """Get the tavily search tool with singleton pattern"""
    global _tavily_tool
    
    if _tavily_tool is None:
        # Set the Tavily API key - make sure this is configured in environment variables
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_api_key:
            raise ValueError("TAVILY_API_KEY environment variable is not set")
        
        _tavily_tool = TavilySearchResults(max_results=5)
    
    return _tavily_tool

def tavily_search(query: Union[str, Dict[str, Any]]) -> Any:
    """
    Run a tavily search with proper error handling and query formatting.
    
    Args:
        query: Either a string or a dictionary with query parameters
        
    Returns:
        Search results from Tavily
    """
    tool = get_tavily_tool()
    
    # Format the query correctly based on input type
    if isinstance(query, str):
        formatted_query = {"query": query}
    elif isinstance(query, dict):
        # If it's already a dict but doesn't have 'query' key, add it
        if "query" not in query and any(query.values()):
            # Use the first non-empty value as the query
            for value in query.values():
                if value:
                    formatted_query = {"query": value}
                    break
        else:
            formatted_query = query
    else:
        # Ensure we always have a valid query format
        formatted_query = {"query": str(query)}
    
    # Add safety parameter for recent content
    if "query" in formatted_query and "recent" not in formatted_query:
        formatted_query["include_domains"] = []
        formatted_query["exclude_domains"] = []
        formatted_query["max_results"] = 5
    
    # Execute the search with proper error handling
    try:
        results = tool.invoke(formatted_query)
        return results
    except Exception as e:
        # Return a friendly error instead of failing completely
        return [{"title": "Search Error", 
                "content": f"Failed to perform search: {str(e)}. Please try a different query.",
                "url": ""}] 