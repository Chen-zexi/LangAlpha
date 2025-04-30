import os
import pandas as pd
import json
import numpy as np
from datetime import date, timedelta, datetime
from dotenv import load_dotenv
from polygon.rest import RESTClient
from polygon.rest.models import TickerSnapshot, Agg # Import necessary models
from mcp.server.fastmcp import FastMCP
from typing import List, Optional, Dict, Any
# Import trading strategies
import trading_strategies
from langgraph.config import get_stream_writer
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
default_to_date = today.isoformat()

TREND_MIN_BARS = 60
MEAN_REVERSION_MIN_BARS = 50
MOMENTUM_MIN_BARS = 126
VOLATILITY_MIN_BARS = 84
STAT_ARB_MIN_BARS = 126
COMBINED_MIN_BARS = 126

def _to_dict(obj):
    """Helper function to convert Polygon objects to dictionaries."""
    if hasattr(obj, '__dict__'):
        data = vars(obj)
        for key, value in data.items():
            if isinstance(value, list):
                data[key] = [_to_dict(item) for item in value]
            elif hasattr(value, '__dict__'):
                data[key] = _to_dict(value)
        return data
    elif isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    else:
        return obj
    
def get_ticker_price(ticker, multiplier=1, timespan='day', from_date='2025-03-13', to_date='2025-03-17', limit=10000) -> pd.DataFrame:
        """
        Get stock data for a ticker from Polygon API
        Args:
            ticker: A ticker symbol or list of ticker symbols
            multiplier: The multiplier for the timespan
            timespan: The timespan for the data
            from_date: The start date for the data
            to_date: The end date for the data
            limit: The maximum number of results to return
        Returns:
            A pandas DataFrame containing the stock data
        """
        aggs = []
        for a in rest_client.list_aggs(ticker=ticker, multiplier=multiplier, timespan=timespan, from_=from_date, to=to_date, limit=limit):
            aggs.append(a)
        if aggs != []:
            df = pd.DataFrame(aggs)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', origin='unix')
            df['ticker'] = ticker
            # Reorder columns to make ticker the first column
            cols = ['ticker'] + [col for col in df.columns if col != 'ticker']
            df = df[cols]
            # Set timestamp as index for proper date reference
            df.set_index('timestamp', inplace=True)
            return df
        else:
            # Return empty DataFrame with ticker column instead of string
            return pd.DataFrame(columns=['ticker', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])



@mcp.tool()
def get_stock_metrics(
    ticker: str,
    multiplier: int = 1,
    timespan: str = 'day',
    from_date: Optional[str] = None,
    to_date: str = default_to_date,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetches aggregate stock data (OHLCV) directly and calculates key stock metrics.

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        multiplier: The size of the timespan multiplier (e.g., 1).
        timespan: The size of the time window (e.g., 'day', 'hour', 'minute').
        from_date: The start date for the aggregates (YYYY-MM-DD). If None, defaults to 180 days ago.
        to_date: The end date for the aggregates (YYYY-MM-DD). Defaults to today.
        limit: The maximum number of base aggregates fetched; affects data used for calculations.

    Returns:
        A dictionary containing calculated stock metrics (e.g., price change %,
        highest/lowest price & date, average volume, volatility, max drawdown, SMA).
        Returns a dictionary with an 'error' key if the client is not initialized, fetching fails,
        or calculations cannot be performed (e.g., insufficient data).
        All numeric values are rounded, and volume figures are formatted (e.g., "1.23M").
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}

    # Capitalize ticker
    ticker = ticker.upper()
    
    # Set default from_date if not provided
    if from_date is None:
        from_date = (date.fromisoformat(to_date) - timedelta(days=180)).isoformat()

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

    try:
        df = pd.DataFrame([vars(a) for a in aggs_list])
        df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
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
    Get the most recent snapshot (trade, quote, minute/day bars) for a single ticker.

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
    writer = get_stream_writer()
    writer.write(f"Retrieving snapshot for {ticker}")

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
    Get the most recent snapshot data for a list of tickers.

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
    writer = get_stream_writer()
    writer.write(f"Retrieving snapshot for: {capitalized_tickers}")
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
    Get the top market movers (gainers or losers) based on percentage change.
    Use with caution, it will likely return penny stocks with high volatility.

    Args:
        direction: The direction of movement ('gainers' or 'losers').
        market_type: The market type (default: 'stocks').
        include_otc: Whether to include OTC securities (default: False).

    Returns:
        A list of dictionaries representing snapshot data for top movers, converted from client response.
        Returns a list containing an error dictionary if the client is not initialized,
        an error occurs, or the direction is invalid.
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving top {direction}")
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
    Get the current trading status of the overall US market and specific exchanges.

    Returns:
        A dictionary containing the current market status details, converted from client response.
        Returns a dictionary with an 'error' key if the client is not initialized or fetching fails.
    """
    writer = get_stream_writer()
    writer.write(f"Checking market status")
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

@mcp.tool()
def get_trend_following_signals(
    ticker: str, 
    end_date: str = default_to_date,
    num_bars: int = TREND_MIN_BARS
) -> Dict[str, Any]:
    """
    Calculate trend following signals for a given ticker.
    
    Uses three Exponential Moving Averages (EMAs) with periods 8, 21, and 55 to determine
    short-term and medium-term trends. Also calculates the Average Directional Index (ADX)
    with a 14-period setting to measure trend strength.

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        end_date: The end date for the analysis (YYYY-MM-DD). Defaults to today.
        num_bars: Number of trading days to analyze, default 60 (minimum recommended).
                  Recommended range is 200-250 for optimal results.

    Returns:
        A dictionary containing trend following signal information including signal direction
        ('bullish', 'bearish', or 'neutral'), confidence level, and relevant metrics.
        
    Note:
        Only trading days (when the market is open) are used for calculations.
        The strategy uses ADX threshold of 20+ to confirm trend strength.
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}
    
    writer = get_stream_writer()
    writer.write(f"Calculating trend following signals for {ticker}")
    # Calculate start date based on end_date and num_bars
    # Add buffer of 2x the bars for weekends, holidays, and data availability
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=num_bars * 2)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    # Get price data with buffer
    df = get_ticker_price(ticker=ticker, from_date=start_date, to_date=end_date, limit=num_bars * 2)
    
    # Limit to requested number of bars (most recent)
    if len(df) > num_bars:
        df = df.iloc[-num_bars:]
    
    # Calculate signals using the adjusted dataframe
    return trading_strategies.calculate_trend_signals(df)

@mcp.tool()
def get_mean_reversion_signals(
    ticker: str, 
    end_date: str = default_to_date,
    num_bars: int = MEAN_REVERSION_MIN_BARS
) -> Dict[str, Any]:
    """
    Calculate mean reversion signals for a given ticker.
    
    Calculates the Z-score of the closing price relative to its 50-period SMA and standard deviation.
    Also computes Bollinger Bands (20-period SMA +/- 2 standard deviations) and RSI for 14 and 28 periods.

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        end_date: The end date for the analysis (YYYY-MM-DD). Defaults to today.
        num_bars: Number of trading days to analyze, default 50 (minimum recommended).
                  Recommended range is 150-250 for more robust statistics.

    Returns:
        A dictionary containing mean reversion signal information including signal direction
        ('bullish', 'bearish', or 'neutral'), confidence level, and relevant metrics.
        
    Note:
        Only trading days (when the market is open) are used for calculations.
        Uses Z-score thresholds of ±1.5 combined with Bollinger Band touches and RSI extremes.
    """
    writer = get_stream_writer()
    writer.write(f"Calculating mean reversion signals for {ticker}")
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}
    
    # Calculate start date based on end_date and num_bars
    # Add buffer of 2x the bars for weekends, holidays, and data availability
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=num_bars * 2)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    # Get price data with buffer
    df = get_ticker_price(ticker=ticker, from_date=start_date, to_date=end_date, limit=num_bars * 2)
    
    # Limit to requested number of bars (most recent)
    if len(df) > num_bars:
        df = df.iloc[-num_bars:]
    
    # Calculate signals using the adjusted dataframe
    return trading_strategies.calculate_mean_reversion_signals(df)

@mcp.tool()
def get_momentum_signals(
    ticker: str, 
    end_date: str = default_to_date,
    num_bars: int = MOMENTUM_MIN_BARS
) -> Dict[str, Any]:
    """
    Calculate momentum signals for a given ticker.
    
    Measures price momentum by calculating and rank-normalizing rolling returns over windows 
    of 1 month (21 days), 3 months (63 days), and 6 months (126 days). Volume momentum is 
    assessed by comparing the current volume to its 21-day moving average.

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        end_date: The end date for the analysis (YYYY-MM-DD). Defaults to today.
        num_bars: Number of trading days to analyze, default 126 (minimum recommended).
                  Recommended range is 252-504 for better seasonality analysis.

    Returns:
        A dictionary containing momentum signal information including signal direction
        ('bullish', 'bearish', or 'neutral'), confidence level, and relevant metrics.
        
    Note:
        Only trading days (when the market is open) are used for calculations.
        Uses rank normalization of returns for each time window to improve weighting scheme.
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}
    
    writer = get_stream_writer()
    writer.write(f"Calculating momentum signals for {ticker}")
    # Calculate start date based on end_date and num_bars
    # Add buffer of 2x the bars for weekends, holidays, and data availability
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=num_bars * 2)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    # Get price data with buffer
    df = get_ticker_price(ticker=ticker, from_date=start_date, to_date=end_date, limit=num_bars * 2)
    
    # Limit to requested number of bars (most recent)
    if len(df) > num_bars:
        df = df.iloc[-num_bars:]
    
    # Calculate signals using the adjusted dataframe
    return trading_strategies.calculate_momentum_signals(df)

@mcp.tool()
def get_volatility_signals(
    ticker: str, 
    end_date: str = default_to_date,
    num_bars: int = VOLATILITY_MIN_BARS
) -> Dict[str, Any]:
    """
    Calculate volatility-based signals for a given ticker.
    
    Calculates historical volatility (21-day annualized standard deviation of returns) and
    identifies the volatility regime by comparing current volatility to its 63-day moving average.
    Also computes the Average True Range (ATR) relative to price and volatility percentiles.

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        end_date: The end date for the analysis (YYYY-MM-DD). Defaults to today.
        num_bars: Number of trading days to analyze, default 84 (minimum recommended).
                  Recommended range is 252-504 for better regime analysis.

    Returns:
        A dictionary containing volatility signal information including signal direction
        ('bullish', 'bearish', or 'neutral'), confidence level, and relevant metrics.
        
    Note:
        Only trading days (when the market is open) are used for calculations.
        Uses a breakout hypothesis (low volatility suggests potential expansion).
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}
    
    writer = get_stream_writer()
    writer.write(f"Calculating volatility signals for {ticker}")
    # Calculate start date based on end_date and num_bars
    # Add buffer of 2x the bars for weekends, holidays, and data availability
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=num_bars * 2)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    # Get price data with buffer
    df = get_ticker_price(ticker=ticker, from_date=start_date, to_date=end_date, limit=num_bars * 2)
    
    # Limit to requested number of bars (most recent)
    if len(df) > num_bars:
        df = df.iloc[-num_bars:]
    
    # Calculate signals using the adjusted dataframe
    return trading_strategies.calculate_volatility_signals(df)

@mcp.tool()
def get_statistical_arbitrage_signals(
    ticker: str, 
    end_date: str = default_to_date,
    num_bars: int = STAT_ARB_MIN_BARS
) -> Dict[str, Any]:
    """
    Calculate statistical arbitrage signals for a given ticker.
    
    Analyzes the distribution of annualized returns using rolling skewness and kurtosis (63-day window).
    Calculates the Hurst exponent to determine if the price series is mean-reverting (H < 0.5),
    trending (H > 0.5), or a random walk (H = 0.5).

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        end_date: The end date for the analysis (YYYY-MM-DD). Defaults to today.
        num_bars: Number of trading days to analyze, default 126 (minimum recommended).
                  Recommended range is 252-756 for more stable estimates.

    Returns:
        A dictionary containing statistical arbitrage signal information including signal direction
        ('bullish', 'bearish', or 'neutral'), confidence level, and relevant metrics.
        
    Note:
        Only trading days (when the market is open) are used for calculations.
        Uses annualized returns for interpretable skewness and kurtosis statistics.
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}
    
    writer = get_stream_writer()
    writer.write(f"Calculating statistical arbitrage signals for {ticker}")
    # Calculate start date based on end_date and num_bars
    # Add buffer of 2x the bars for weekends, holidays, and data availability
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=num_bars * 2)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    # Get price data with buffer
    df = get_ticker_price(ticker=ticker, from_date=start_date, to_date=end_date, limit=num_bars * 2)
    
    # Limit to requested number of bars (most recent)
    if len(df) > num_bars:
        df = df.iloc[-num_bars:]
    
    # Calculate signals using the adjusted dataframe
    return trading_strategies.calculate_stat_arb_signals(df)

@mcp.tool()
def get_all_trading_signals(
    ticker: str, 
    end_date: str = default_to_date,
    num_bars: int = COMBINED_MIN_BARS
) -> Dict[str, Any]:
    """
    Calculate all trading signals and provide a consensus view for a given ticker.
    
    Combines signals from trend following, mean reversion, momentum, volatility analysis,
    and statistical arbitrage strategies to form a comprehensive trading signal.

    Args:
        ticker: The ticker symbol (e.g., AAPL).
        end_date: The end date for the analysis (YYYY-MM-DD). Defaults to today.
        num_bars: Number of trading days to analyze, default 126 (minimum recommended).
                  Recommended range is 252-504 for optimal strategy performance.

    Returns:
        A dictionary containing signals from all strategies (the confidence score for each strategy is ranged from 0 to 3), and a consensus signal with a confidence level based on the weighted combination of all strategy signals (normalized to 0-1).
        
    Note:
        Only trading days (when the market is open) are used for calculations.
        Each strategy uses its recommended number of bars, appropriately scaled
        based on the provided num_bars parameter.
    """
    if rest_client is None:
        return {"error": "Polygon RESTClient is not initialized. Check API Key."}
    
    writer = get_stream_writer()
    writer.write(f"Calculating all trading signals for {ticker}")
    # Calculate start date based on end_date and the largest possible num_bars needed
    # Use 2x buffer for weekends, holidays, and data availability
    # Use max of all strategy minimums to ensure adequate data
    max_bars_needed = max(TREND_MIN_BARS, MEAN_REVERSION_MIN_BARS, MOMENTUM_MIN_BARS, 
                         VOLATILITY_MIN_BARS, STAT_ARB_MIN_BARS, num_bars)
    
    start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=max_bars_needed * 2)
    start_date = start_dt.strftime('%Y-%m-%d')
    
    # Get price data with buffer
    df = get_ticker_price(ticker=ticker, from_date=start_date, to_date=end_date, limit=max_bars_needed * 2)
    
    # Limit to requested number of bars (most recent)
    if len(df) > num_bars:
        df = df.iloc[-num_bars:]
    
    signals = trading_strategies.get_combined_signals(df)
    
    return {
        "ticker": ticker,
        "as_of_date": end_date,
        "lookback_days": num_bars,
        "strategies": signals["strategies"],
        "consensus": signals["consensus"]
    }


if __name__ == "__main__":
    mcp.run('stdio')