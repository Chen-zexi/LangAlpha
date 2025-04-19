import os
import pandas as pd
import json
import numpy as np
from datetime import date, timedelta
from dotenv import load_dotenv
from polygon import RESTClient
from polygon.rest.models import TickerSnapshot, Agg # Import necessary models
from mcp.server.fastmcp import FastMCP
from typing import List, Optional, Dict, Any

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Polygon")

# --- API Key Handling & Client Initialization ---
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
rest_client = None
if not POLYGON_API_KEY:
    print("Warning: POLYGON_API_KEY environment variable not set. Polygon tools will likely fail.")
else:
    try:
        rest_client = RESTClient(api_key=POLYGON_API_KEY)
        print("Polygon RESTClient initialized successfully.")
    except Exception as e:
        print(f"Error initializing Polygon RESTClient: {e}")
        # Client remains None, tools should check for this


today = date.today()
seven_days_ago = today - timedelta(days=7)
default_to_date = today.isoformat()
default_from_date = seven_days_ago.isoformat()

def _to_dict(obj):
    """Helper function to convert Polygon objects to dictionaries."""
    if hasattr(obj, '__dict__'):
        # Attempt basic conversion using __dict__
        data = vars(obj)
        # Recursively convert nested objects
        for key, value in data.items():
            if isinstance(value, list):
                data[key] = [_to_dict(item) for item in value]
            elif hasattr(value, '__dict__'):
                data[key] = _to_dict(value)
        return data
    elif isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    else:
        # Return basic types as is
        return obj

@mcp.tool()
def get_stock_metrics(
    ticker: str,
    multiplier: int = 1,
    timespan: str = 'day',
    from_date: str = default_from_date,
    to_date: str = default_to_date,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetches aggregate stock data (OHLCV) directly via RESTClient and calculates key financial metrics.

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        multiplier: The size of the timespan multiplier (e.g., 1).
        timespan: The size of the time window (e.g., 'day', 'hour', 'minute').
        from_date: The start date for the aggregates (YYYY-MM-DD). Defaults to 7 days ago.
        to_date: The end date for the aggregates (YYYY-MM-DD). Defaults to today.
        limit: The maximum number of base aggregates fetched; affects data used for calculations.

    Returns:
        A dictionary containing calculated financial metrics (e.g., price change %,
        highest/lowest price & date, average volume, volatility, max drawdown, SMA).
        Returns a dictionary with an 'error' key if the client is not initialized, fetching fails,
        or calculations cannot be performed (e.g., insufficient data).
        All numeric values are rounded, and volume figures are formatted (e.g., "1.23M").
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}

    # Capitalize ticker
    ticker = ticker.upper()

    aggs_list = []
    try:
        # Fetch aggregates using the RESTClient directly
        for a in rest_client.list_aggs(
            ticker=ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_=from_date,
            to=to_date,
            limit=limit,
            sort='asc' # Ensure data is sorted for calculations
        ):
            aggs_list.append(a)

    except Exception as e:
        print(f"Error fetching aggregates via RESTClient for {ticker}: {e}")
        return {"error": f"Failed to fetch aggregates for {ticker}: {str(e)}"}

    if not aggs_list:
        return {"error": f"No aggregate data found for {ticker} in the specified range."}

    # --- Re-implement Data Processing and Metric Calculation --- 
    try:
        # Convert Agg objects to dictionaries and create DataFrame
        df = pd.DataFrame([vars(a) for a in aggs_list])
        # Rename columns if necessary (adjust based on `vars(a)` output)
        # Assuming vars(a) gives keys like 't', 'o', 'h', 'l', 'c', 'v'
        df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)

        # --- Data Cleaning and Preparation (copied from PolygonDataProvider) ---
        df.dropna(subset=['timestamp', 'open', 'high', 'low', 'close', 'volume'], inplace=True)

        if df.empty:
             return {"error": f"No valid aggregate data points found for {ticker} after initial processing."}

        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('date', inplace=True)

        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        df.dropna(subset=numeric_cols, inplace=True)

        if df.empty:
             return {"error": f"Data for {ticker} could not be processed numerically."}

        if len(df) < 2:
             basic_info = {
                'ticker': ticker,
                'data_points': len(df),
                'message': f"Insufficient data points ({len(df)}) to calculate detailed metrics.",
                'data_start_date': df.index.min().strftime('%Y-%m-%d') if not df.empty else None,
                'data_end_date': df.index.max().strftime('%Y-%m-%d') if not df.empty else None,
                'last_close_price': float(df['close'].iloc[-1]) if not df.empty else None,
                'total_volume': int(df['volume'].sum()) if not df.empty else None
             }
             if basic_info['total_volume'] is not None:
                 basic_info['total_volume'] = f"{basic_info['total_volume'] / 1_000_000:.2f}M"
             return basic_info
        # --- Metric Calculation Logic (copied from PolygonDataProvider) --- 
        metrics = {}
        metrics['ticker'] = ticker
        metrics['data_start_date'] = df.index.min().strftime('%Y-%m-%d')
        metrics['data_end_date'] = df.index.max().strftime('%Y-%m-%d')
        metrics['period_days'] = (df.index.max() - df.index.min()).days + 1 if timespan == 'day' else None
        metrics['data_points_used'] = len(df)

        first_open = df['open'].iloc[0]
        last_close = df['close'].iloc[-1]
        metrics['first_open_price'] = first_open
        metrics['last_close_price'] = last_close
        metrics['overall_change_percent'] = ((last_close - first_open) / first_open) * 100 if first_open != 0 else None

        metrics['highest_price'] = df['high'].max()
        metrics['highest_price_date'] = df['high'].idxmax().strftime('%Y-%m-%d')
        metrics['lowest_price'] = df['low'].min()
        metrics['lowest_price_date'] = df['low'].idxmin().strftime('%Y-%m-%d')

        metrics['average_volume'] = df['volume'].mean()
        metrics['total_volume'] = df['volume'].sum()

        returns = df['close'].pct_change().dropna()
        metrics['volatility_std_dev'] = None
        metrics['annualized_volatility_percent'] = None
        if not returns.empty and len(returns) > 1:
            daily_std_dev = returns.std()
            periods_per_year = {
                'minute': 252 * 6.5 * 60, 'hour': 252 * 6.5, 'day': 252,
                'week': 52, 'month': 12, 'quarter': 4, 'year': 1
            }.get(timespan, 252)
            metrics['volatility_std_dev'] = daily_std_dev
            metrics['annualized_volatility_percent'] = daily_std_dev * np.sqrt(periods_per_year) * 100

        cumulative_max = df['close'].cummax()
        drawdown = (df['close'] - cumulative_max) / cumulative_max
        max_drawdown_percent = drawdown.min() * 100
        metrics['max_drawdown_percent'] = None
        metrics['max_drawdown_date'] = None
        if pd.notna(max_drawdown_percent) and not np.isinf(max_drawdown_percent) and cumulative_max.iloc[0] != 0:
            metrics['max_drawdown_percent'] = max_drawdown_percent
            if drawdown.notna().any():
                 try:
                     metrics['max_drawdown_date'] = drawdown.idxmin().strftime('%Y-%m-%d')
                 except ValueError:
                     pass # Keep as None

        sma_period = metrics['data_points_used']
        metrics[f'sma_{sma_period}_period'] = df['close'].rolling(window=sma_period).mean().iloc[-1] if len(df) >= sma_period else None

        # --- Final Formatting (copied from PolygonDataProvider) --- 
        volume_keys = {'average_volume', 'total_volume'}
        formatted_metrics = {}
        for key, value in metrics.items():
            if value is None:
                formatted_metrics[key] = None
                continue

            if isinstance(value, (np.floating, float)):
                py_float = float(value)
                if key in volume_keys:
                    formatted_metrics[key] = f"{py_float / 1_000_000:.2f}M"
                else:
                    formatted_metrics[key] = round(py_float, 2)
            elif isinstance(value, (np.integer, int)):
                py_int = int(value)
                if key in volume_keys:
                    formatted_metrics[key] = f"{py_int / 1_000_000:.2f}M"
                else:
                    formatted_metrics[key] = py_int
            else:
                 formatted_metrics[key] = value

        return formatted_metrics

    except Exception as e:
        print(f"Error calculating metrics for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Failed to calculate metrics for {ticker}: {str(e)}"}

@mcp.tool()
def get_ticker_snapshot(ticker: str) -> Dict[str, Any]:
    """
    Get the most recent snapshot (trade, quote, minute/day bars) for a single ticker using RESTClient.

    Args:
        ticker: The ticker symbol (e.g., AAPL).

    Returns:
        A dictionary containing the snapshot data for the ticker, converted from the client response.
        Returns a dictionary with an 'error' key if the client is not initialized,
        the ticker is not found, or another error occurs.
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}

    # Capitalize ticker
    ticker = ticker.upper()

    try:
        # Call the RESTClient method directly
        snapshot_obj = rest_client.get_snapshot_ticker(market_type="stocks", ticker=ticker)
        # Convert the returned object (likely a TickerSnapshot) to a dictionary
        return _to_dict(snapshot_obj)
    except Exception as e:
        print(f"Error in get_ticker_snapshot MCP tool for {ticker}: {e}")
        # Handle potential 404 or other client errors gracefully
        if hasattr(e, 'response') and e.response.status_code == 404:
            return {"error": f"Snapshot data not found for ticker: {ticker}"}
        return {"error": f"An unexpected error occurred while fetching snapshot for {ticker}: {str(e)}"}

@mcp.tool()
def get_all_tickers_snapshot(tickers: List[str], include_otc: bool = False) -> List[Dict[str, Any]]:
    """
    Get the most recent snapshot data for all tickers in a given market using RESTClient.

    Args:
        tickers: A list of ticker symbols to fetch snapshots for.
        include_otc: Whether to include OTC securities in the response (default: False).

    Returns:
        A list of dictionaries representing snapshot data for all tickers in the market.
        Each dictionary is converted from the client's response objects.
        Returns a list containing an error dictionary if the client is not initialized or an error occurs.
    """
    if rest_client is None:
        return [{"error": "Polygon RESTClient is not initialized. Check API Key."}]

    # Capitalize all tickers in the list
    capitalized_tickers = [t.upper() for t in tickers]

    try:
        # Call the RESTClient method directly
        snapshot_iterator = rest_client.get_snapshot_all(
            market_type='stocks',
            tickers=capitalized_tickers,
            include_otc=include_otc
        )
        # Convert the iterator of snapshot objects to a list of dictionaries
        snapshots_list = [_to_dict(s) for s in snapshot_iterator]
        return snapshots_list

    except Exception as e:
        print(f"Error in get_all_tickers_snapshot MCP tool: {e}")
        return [{"error": f"An unexpected error occurred: {str(e)}"}]

@mcp.tool()
def get_market_movers(direction: str, include_otc: bool = False) -> List[Dict[str, Any]]:
    """
    Get the top market movers (gainers or losers) based on percentage change using RESTClient.

    Args:
        direction: The direction of movement ('gainers' or 'losers').
        market_type: The market type (default: 'stocks').
        include_otc: Whether to include OTC securities (default: False).

    Returns:
        A list of dictionaries representing snapshot data for top movers, converted from client response.
        Returns a list containing an error dictionary if the client is not initialized,
        an error occurs, or the direction is invalid.
    """
    if rest_client is None:
        return [{"error": "Polygon RESTClient is not initialized. Check API Key."}]
    if direction not in ['gainers', 'losers']:
        return [{"error": "Invalid direction specified. Use 'gainers' or 'losers'."}]
    try:
        # Call the RESTClient method directly
        movers_iterator = rest_client.get_snapshot_direction(
            market_type='stocks',
            direction=direction,
            include_otc=include_otc
            )
        # Convert the iterator of snapshot objects to a list of dictionaries
        movers_list = [_to_dict(m) for m in movers_iterator]
        return movers_list

    except Exception as e:
        print(f"Error in get_market_movers MCP tool for {direction}: {e}")
        return [{"error": f"An unexpected error occurred: {str(e)}"}]

@mcp.tool()
def get_market_status() -> Dict[str, Any]:
    """
    Get the current trading status of the overall US market and specific exchanges using RESTClient.

    Returns:
        A dictionary containing the current market status details, converted from client response.
        Returns a dictionary with an 'error' key if the client is not initialized or fetching fails.
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}
    try:
        # Call the RESTClient method directly
        status_obj = rest_client.get_market_status()
        # Convert the returned object to a dictionary
        return _to_dict(status_obj)
    except Exception as e:
        print(f"Error in get_market_status MCP tool: {e}")
        return {"error": f"An unexpected error occurred: {str(e)}"}

#@mcp.tool()
# def get_stock_financials(
#     ticker: str,
#     timeframe: Optional[str] = 'quarterly', # 'annual', 'quarterly', 'ttm'
#     limit: Optional[int] = 10 # Max 100 for this endpoint, fixed syntax
# ) -> List[Dict[str, Any]]:
#     """
#     Get historical financial data for a stock ticker from SEC filings using RESTClient (EXPERIMENTAL API).
#     Manually limits results to the specified `limit` parameter.

#     Args:
#         ticker: The ticker symbol (e.g., AAPL).
#         timeframe: Query by timeframe (annual, quarterly, ttm). Defaults to 'quarterly'.
#         limit: Limit the number of results returned (default: 10, max: 100).

#     Returns:
#         A list of dictionaries, where each dictionary represents a financial report entry,
#         converted from the client's response objects. The list length will not exceed `limit`.
#         Returns a list containing an error dictionary if the client is not initialized or fetching fails.
#     """
#     if rest_client is None:
#         return [{"error": "Polygon RESTClient is not initialized. Check API Key."}]

#     # Capitalize ticker
#     ticker = ticker.upper()

#     try:
#         # Use the client's get_stock_financials method
#         # We still pass the limit to the API, even if it might be ignored
#         financials_iterator = rest_client.vx.list_stock_financials(
#             ticker=ticker, # Use capitalized ticker
#             timeframe=timeframe,
#             order='desc', # Typically want most recent first
#             include_sources=False,
#             limit=limit, # Pass limit to API
#         )

#         # Convert iterator to a list of dictionaries
#         financials_list = [_to_dict(f) for f in financials_iterator]

#         # Manually enforce the limit *after* receiving results
#         return financials_list[:limit]

#     except Exception as e:
#         print(f"Error fetching stock financials for {ticker}: {e}") # Ticker in log is capitalized
#         # Handle potential 404 or other client errors gracefully
#         if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 404:
#              return [{"error": f"Financial data not found for ticker: {ticker}"}] # Ticker in error is capitalized
#         return [{"error": f"Failed to fetch stock financials for {ticker}: {str(e)}"}] # Ticker in error is capitalized


# --- Main Execution Block ---
if __name__ == "__main__":
    # Add argument parsing if needed for port, host, etc.
    mcp.run('stdio')