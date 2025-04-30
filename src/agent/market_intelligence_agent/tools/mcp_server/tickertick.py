from mcp.server.fastmcp import FastMCP
from langgraph.config import get_stream_writer
from typing import List, Optional
#from src.mcp_server.tickertick_mcp.tickertick import Tickertick
import requests
import asyncio
from datetime import datetime

# Create the MCP server with a meaningful name
mcp = FastMCP("TickertickMCP")

# Setup API endpoints
FEED_URL = 'https://api.tickertick.com/feed'
TICKERS_URL = 'https://api.tickertick.com/tickers'
RATE_LIMIT = 10  # 10 requests per minute limit

def get_feed(query, limit=30, last_id=None):
    """Get feed data from Tickertick API"""
    url = f"{FEED_URL}?q={query}"
    
    if limit:
        url += f"&n={limit}"
    
    if last_id:
        url += f"&last={last_id}"
        
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return convert_timestamp_ms_to_iso(data)
    else:
        return {"error": f"API request failed with status code {response.status_code}"}
    
def convert_timestamp_ms_to_iso(response):
    """Convert timestamp in milliseconds to ISO format"""
    for story in response['stories']:
        if 'time' in story:
            timestamp_sec = story['time'] / 1000
            story['time'] = datetime.utcfromtimestamp(timestamp_sec).isoformat()
    return response

def get_ticker_news(ticker, limit=30):
    """Get news for a specific ticker"""
    query = f"z:{ticker}"
    return get_feed(query, limit)

def get_broad_ticker_news(ticker, limit=30):
    """Get broader news for a specific ticker"""
    query = f"tt:{ticker}"
    return get_feed(query, limit)

def get_news_from_source(source, limit=30):
    """Get news from a specific source"""
    query = f"s:{source}"
    return get_feed(query, limit)

def get_news_for_multiple_tickers(tickers, limit=30):
    """Get news for multiple tickers"""
    ticker_terms = [f"tt:{ticker}" for ticker in tickers]
    query = f"(or {' '.join(ticker_terms)})"
    return get_feed(query, limit)

def get_curated_news(limit=30):
    """Get curated news from top financial/technology sources"""
    query = "T:curated"
    return get_feed(query, limit)

def get_entity_news(entity, limit=30):
    """Get news about a specific entity"""
    # Replace spaces with underscores as required by the API
    entity = entity.lower().replace(" ", "_")
    query = f"E:{entity}"
    return get_feed(query, limit)

def search_tickers(query, limit=5):
    """Search for tickers matching the query"""
    url = f"{TICKERS_URL}?p={query}&n={limit}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"API request failed with status code {response.status_code}"}

@mcp.tool()
def get_ticker_news_tool(ticker: str, limit: int = 10) -> dict:
    """
    Get news for a specific ticker symbol.
    
    Args:
        ticker: The ticker symbol (e.g., AAPL, MSFT, TSLA)
        limit: Maximum number of news items to return (default: 10, max: 50)
        
    Returns:
        A dictionary containing news items related to the ticker
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving news for {ticker}")
    return get_ticker_news(ticker, limit)

@mcp.tool()
def get_broad_ticker_news_tool(ticker: str, limit: int = 10) -> dict:
    """
    Get broader news for a specific ticker symbol.
    
    Args:
        ticker: The ticker symbol (e.g., AAPL, MSFT, TSLA)
        limit: Maximum number of news items to return (default: 10, max: 50)
        
    Returns:
        A dictionary containing broader news items related to the ticker
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving broader news for {ticker}")
    return get_broad_ticker_news(ticker, limit)

@mcp.tool()
def get_news_from_source_tool(source: str, limit: int = 10) -> dict:
    """
    Get news from a specific source.
    
    Args:
        source: The news source (e.g., bloomberg, wsj, cnbc)
        limit: Maximum number of news items to return (default: 10, max: 50)
        
    Returns:
        A dictionary containing news items from the specified source
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving news from {source}")
    return get_news_from_source(source, limit)

@mcp.tool()
def get_news_for_multiple_tickers_tool(tickers: List[str], limit: int = 10) -> dict:
    """
    Get news for multiple ticker symbols.
    
    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "TSLA"])
        limit: Maximum number of news items to return (default: 10, max: 50)
        
    Returns:
        A dictionary containing news items related to any of the specified tickers
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving news for: {tickers}")
    return get_news_for_multiple_tickers(tickers, limit)

@mcp.tool()
def get_curated_news_tool(limit: int = 10) -> dict:
    """
    Get curated news from top financial/technology sources. This can be helpful to get a broad overview of the market.
    
    Args:
        limit: Maximum number of news items to return (default: 10, max: 50)
        
    Returns:
        A dictionary containing curated news items
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving curated news")
    return get_curated_news(limit)

@mcp.tool()
def get_entity_news_tool(entity: str, limit: int = 10) -> dict:
    """
    Get news about a specific entity (person, etc.)
    
    Args:
        entity: The entity name (e.g."Elon Musk", "Trump")
        limit: Maximum number of news items to return (default: 10, max: 50)
        
    Returns:
        A dictionary containing news items related to the entity
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving news about {entity}")
    return get_entity_news(entity, limit)

@mcp.tool()
def search_tickers_tool(query: str, limit: int = 5) -> dict:
    """
    Search for tickers matching the query.
    
    Args:
        query: The search query (e.g., "Apple", "TSLA")
        limit: Maximum number of results to return (default: 5, max: 20)
        
    Returns:
        A dictionary containing matching ticker symbols
    """
    writer = get_stream_writer()
    writer.write(f"Searching for tickers matching {query}")
    return search_tickers(query, limit)

# Add this to run the server with stdio transport when executed directly
if __name__ == "__main__":
    mcp.run(transport="stdio") 