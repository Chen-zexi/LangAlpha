from __future__ import annotations
from datetime import date
from typing import Dict, Any, List, Sequence, Union, Optional
import os
import requests
import csv
from dotenv import load_dotenv
from math import isnan
from statistics import mean
from mcp.server.fastmcp import FastMCP

# Setup
load_dotenv()
API_KEY = os.getenv("FINANCIALMODELINGPREP_API_KEY")
BASE_URL = "https://financialmodelingprep.com/stable/"

if not API_KEY:
    raise EnvironmentError(
        "Missing FINANCIALMODELINGPREP_API_KEY in environment. "
    )


# Helper functions

def _get(endpoint: str) -> Dict[str, Any]:
    resp = requests.get(BASE_URL + endpoint+"&apikey="+API_KEY, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Check for API error messages or notes
    if any(k in data for k in ("Note", "Information", "Error Message")):
        # Consolidate potential messages into one string for the exception
        messages = []
        for key in ("Note", "Information", "Error Message"):
            if key in data and data[key]:
                messages.append(f"{key}: {data[key]}")
        if messages:
            raise RuntimeError(f"Financial Modeling Prep API message: {'; '.join(messages)}")
    return data

def _process_item(item):
    if 'data' in item and isinstance(item['data'], dict):
        # Sort and normalize
        sorted_data = dict(sorted(
            ((k, v/1_000_000) for k, v in item['data'].items()),
            key=lambda x: x[1], reverse=True
        ))
        item['data'] = sorted_data
    return item
def revenue_product_segmentation(symbol: str, num_years: int=0) -> Dict[str, Any]:
    endpointbase = "revenue-product-segmentation"
    endpoint = endpointbase+"?symbol="+symbol
    resp = _get(endpoint)
    if isinstance(resp, list):
        filtered = [_process_item(item) for item in resp[0:num_years]]
        return filtered
    return resp

def revenue_geographic_segmentation(symbol: str, num_years: int=0) -> Dict[str, Any]:
    endpointbase = "revenue-geographic-segmentation"
    endpoint = endpointbase+"?symbol="+symbol
    resp = _get(endpoint)
    if isinstance(resp, list):
        filtered = [_process_item(item) for item in resp[0:num_years]]
        return filtered
    return resp

def price_target_consensus(symbol: str) -> Dict[str, Any]:
    endpointbase = "price-target-consensus"
    endpoint = endpointbase+"?symbol="+symbol
    resp = _get(endpoint)
    return resp

def price_target_consensus(symbol: str) -> Dict[str, Any]:
    endpointbase = "price-target-consensus"
    endpoint = endpointbase+"?symbol="+symbol
    resp = _get(endpoint)
    return resp

def grades_consensus(symbol: str) -> Dict[str, Any]:
    endpointbase = "grades-consensus"
    endpoint = endpointbase+"?symbol="+symbol
    resp = _get(endpoint)
    return resp
    
def grades_historical(symbol: str, num_months: int=3) -> Dict[str, Any]:
    endpointbase = "grades-historical"
    endpoint = endpointbase+"?symbol="+symbol
    resp = _get(endpoint)
    if isinstance(resp, list):
        filtered = resp[0:num_months]
        return filtered
    return resp


    
# Wrapper functions exposed as tools
mcp = FastMCP("FinancialModelingPrepTools")

@mcp.tool()
def get_revenue_by_product(symbol: str, num_years: int=1) -> Dict[str, Any]:
    """
    Get the revenue in millions by product for a given stock symbol and number of years for the range.
    Note: The data is normalized by 1 million.
    Parameters:
    ----------
    symbol : str
        The stock ticker symbol, Required.
    num_years : int
        The number of years to filter the results by. Default is 1. Change if you want more or less.
    """
    return revenue_product_segmentation(symbol, num_years)

@mcp.tool()
def get_revenue_by_geographic_region(symbol: str, num_years: int=1) -> Dict[str, Any]:
    """
    Get the revenue in millions by geographic region for a given stock symbol and number of years for the range.
    Note: The data is normalized by 1 million.
    Parameters:
    ----------
    symbol : str
        The stock ticker symbol, Required.
    num_years : int
        The number of years to filter the results by. Default is 1. Change if you want more or less.
    """
    return revenue_geographic_segmentation(symbol, num_years)

@mcp.tool()
def get_price_target_consensus(symbol: str) -> Dict[str, Any]:
    """
    Get the price target consensus for a given stock symbol.
    Parameters:
    ----------
    symbol : str
        The stock ticker symbol, Required.
    """
    return price_target_consensus(symbol)

@mcp.tool()
def get_grades_consensus(symbol: str) -> Dict[str, Any]:
    """
    Get the grades consensus for a given stock symbol.
    Useful to get the latest grades for a stock by sell-side analyst.
    Parameters:
    ----------
    symbol : str
        The stock ticker symbol, Required.
    """
    return grades_consensus(symbol)

@mcp.tool()
def get_grades_historical(symbol: str, num_months: int=3) -> Dict[str, Any]:
    """
    Get the grades historical for a given stock symbol by number of months.
    Useful to observe the changes of grades over time.
    Parameters:
    ----------
    symbol : str
        The stock ticker symbol, Required.
    num_months : int
        The number of months to filter the results by. Default is 3. Change if you want more or less.
    """
    return grades_historical(symbol, num_months)


# __all__ can be useful for `from module import *` but less critical for tool-based exposure
__all__: List[str] = [
    "get_revenue_by_product",
    "get_revenue_by_geographic_region",
    "get_price_target_consensus",
    "get_grades_consensus",
    "get_grades_historical"
]

if __name__ == "__main__":
    mcp.run(transport="stdio")