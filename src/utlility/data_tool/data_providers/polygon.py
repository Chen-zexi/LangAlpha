import pandas as pd
import requests
import numpy as np
import time
import json
from datetime import date, timedelta # Added imports
from requests.exceptions import HTTPError
from urllib3.exceptions import MaxRetryError # Import MaxRetryError
from polygon import RESTClient
from polygon.rest.models import (
    TickerSnapshot,
    TickerNews,
    Agg
)
import os
from dotenv import load_dotenv
from src.data_tool.data_models import (
    insights,
    CompanyNews,
    CompanyNewsResponse,
)
from src.database_tool.db_operations import DataOperations # Added import
from typing import List, Optional, Dict, Any # Added import


load_dotenv()

# Calculate default dates (today and 7 days ago) outside class for potential reuse
today = date.today()
seven_days_ago = today - timedelta(days=7)
default_to_date = today.isoformat()
default_from_date = seven_days_ago.isoformat()


class polygon:
    def __init__(self):
        self.api_key = os.getenv('POLYGON_API_KEY')
        if self.api_key is None:
            raise ValueError("POLYGON_API_KEY is not set")
        else:
            print("POLYGON_API_KEY is set")
        self.client = RESTClient(api_key=self.api_key)
        self.db_ops = DataOperations() # Instantiate DataOperations
    
    def get_data(self, ticker, multiplier=1, timespan='day', from_date='2025-03-13', to_date='2025-03-17', limit=10000) -> pd.DataFrame:
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
        for a in self.client.list_aggs(ticker=ticker, multiplier=multiplier, timespan=timespan, from_=from_date, to=to_date, limit=limit):
            aggs.append(a)
        if aggs != []:
            df = pd.DataFrame(aggs)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', origin='unix')
            df['ticker'] = ticker
            # Reorder columns to make ticker the first column
            cols = ['ticker'] + [col for col in df.columns if col != 'ticker']
            df = df[cols]
            return df
        else:
            # Return empty DataFrame with ticker column instead of string
            return pd.DataFrame(columns=['ticker', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def get_stock_metrics(self,
                          ticker: str,
                          multiplier: int = 1,
                          timespan: str = 'day',
                          from_date: str = default_from_date,
                          to_date: str = default_to_date,
                          limit: int = 100) -> Dict[str, Any]:
        """
        Fetches aggregate stock data (OHLCV) for a ticker and calculates key financial metrics.

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
        Returns a dictionary with an error message if fetching fails or calculations
        cannot be performed (e.g., insufficient data).
        """
        aggs_list = []
        try:
            # Fetch aggregates
            for a in self.client.list_aggs(
                ticker=ticker,
                multiplier=multiplier,
                timespan=timespan,
                from_=from_date,
                to=to_date,
                limit=limit,
                sort='asc'
            ):
                aggs_list.append(a)

        except Exception as e:
            print(f"Error fetching aggregates for {ticker}: {e}")
            return {"error": f"Failed to fetch aggregates for {ticker}: {str(e)}"}

        if not aggs_list:
            return {"error": f"No aggregate data found for {ticker} in the specified range."}

        # --- Process Data and Calculate Metrics ---
        try:
            # Create and prepare DataFrame
            df = pd.DataFrame([vars(a) for a in aggs_list]) # Use vars() for attributes
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

            # Check for sufficient data points
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
                 # Format volume in the basic info as well
                 if basic_info['total_volume'] is not None:
                     basic_info['total_volume'] = f"{basic_info['total_volume'] / 1_000_000:.2f}M"
                 return basic_info

            # --- Calculate Metrics ---
            metrics = {}
            metrics['ticker'] = ticker
            metrics['data_start_date'] = df.index.min().strftime('%Y-%m-%d')
            metrics['data_end_date'] = df.index.max().strftime('%Y-%m-%d')
            metrics['period_days'] = (df.index.max() - df.index.min()).days + 1 if timespan == 'day' else None
            metrics['data_points_used'] = len(df)

            # Price Change
            first_open = df['open'].iloc[0]
            last_close = df['close'].iloc[-1]
            metrics['first_open_price'] = first_open
            metrics['last_close_price'] = last_close
            metrics['overall_change_percent'] = ((last_close - first_open) / first_open) * 100 if first_open != 0 else None

            # High/Low
            metrics['highest_price'] = df['high'].max()
            metrics['highest_price_date'] = df['high'].idxmax().strftime('%Y-%m-%d')
            metrics['lowest_price'] = df['low'].min()
            metrics['lowest_price_date'] = df['low'].idxmin().strftime('%Y-%m-%d')

            # Volume
            metrics['average_volume'] = df['volume'].mean()
            metrics['total_volume'] = df['volume'].sum()

            # Volatility
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

            # Max Drawdown
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

            # SMA
            sma_period = metrics['data_points_used']
            metrics[f'sma_{sma_period}_period'] = df['close'].rolling(window=sma_period).mean().iloc[-1] if len(df) >= sma_period else None

            # --- Final Formatting ---
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
                        formatted_metrics[key] = py_int # Keep other ints (period_days, data_points_used)
                else:
                     formatted_metrics[key] = value # Keep strings (ticker, dates) as is

            return formatted_metrics

        except Exception as e:
            print(f"Error calculating metrics for {ticker}: {e}")
            return {"error": f"Failed to calculate metrics for {ticker}: {str(e)}"}

    def get_data_multiple(self, tickers, multiplier=1, timespan='day', from_date='2025-03-13', to_date='2025-03-17', limit=100000):
        all_data = pd.DataFrame()
        for ticker in tickers:
            df = self.get_data(ticker, multiplier, timespan, from_date, to_date, limit)
            if not df.empty:
                all_data = pd.concat([all_data, df], ignore_index=True)
            time.sleep(10)
        return all_data
    
    def get_news(self, ticker, from_date=None, to_date=None, order="asc", limit=1000, strict=True):
        """
        Get news for a ticker or tickers.
        
        Args:
            ticker: A ticker symbol or list of ticker symbols
            from_date: Start date in format YYYY-MM-DD
            to_date: End date in format YYYY-MM-DD
            order: Order of results, "asc" or "desc"
            limit: Maximum number of results to return
            strict: If True, only return news that has insight_tickers matching the ticker
        Returns:
            Tuple containing (news_data, news_df) where:
            - news_data is the full response dictionary using polygon_news_response model
            - news_df is a DataFrame with key information
        """
        # Get news data
        api_response = self.client.list_ticker_news(
            ticker=ticker,
            published_utc_gte=from_date,
            published_utc_lte=to_date,
            order=order,
            limit=limit,
            sort="published_utc",
        )
        
        # Convert API response directly to our model format
        news_list = []
        for n in api_response:
            # Convert the response object to JSON string then to dict
            news_json = json.loads(json.dumps(n, default=lambda o: o.__dict__))
            
            news_json['publisher'] = news_json['publisher']['name']
                
            news_list.append(news_json)
        
        # Create a response dictionary and parse with Pydantic model
        news_data_dict = {
            "count": len(news_list),
            "results": news_list,
        }
        
        try:
            news_data = CompanyNewsResponse(**news_data_dict)
            news_df = pd.DataFrame(news_data.model_dump()['results'])
            
            # Prepare the DataFrame for insertion
            if not news_df.empty:
                news_df = news_df.rename(columns={'id': 'polygon_id'})
                news_df['ticker'] = ticker
                
                # Convert ISO 8601 datetime format (2025-03-01T00:05:27Z) to MySQL compatible format (2025-03-01 00:05:27)
                if 'published_utc' in news_df.columns:
                    news_df['published_utc'] = pd.to_datetime(news_df['published_utc']).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Convert list/dict columns to JSON strings for DB storage
                for col in ['tickers', 'keywords', 'insights']:
                    if col in news_df.columns:
                        news_df[col] = news_df[col].apply(json.dumps)
                
                # Insert data into the database
                self.db_ops.insert_company_news(news_df, ticker=ticker)

        except Exception as e:
            print(f"Error processing or inserting news data: {e}")
            news_df = pd.DataFrame()
            news_data = CompanyNewsResponse(count=0, results=[])
        
        return news_data, news_df

    def get_ticker_snapshot(self, ticker: str) -> Dict[str, Any]:
        """
        Get the most recent snapshot (trade, quote, minute/day bars) for a single ticker.

        Args:
            ticker: The ticker symbol (e.g., AAPL).

        Returns:
            A dictionary containing the snapshot data for the ticker.
            Returns a dictionary with an error message if the ticker is not found or an error occurs.
        """
        try:
            snapshot = self.client.get_snapshot_ticker(market_type="stocks", ticker=ticker)

            return snapshot

        except Exception as e:
            print(f"Error fetching snapshot for {ticker}: {e}")
            return {"error": f"Failed to fetch snapshot for {ticker}: {str(e)}"}

    def get_all_tickers_snapshot(self, market_type: str = 'stocks', tickers: Optional[List[str]] = None, include_otc: bool = False) -> List[Dict[str, Any]]:
        """
        Get the most recent snapshot data for all tickers or a specified list of tickers.

        Args:
            tickers: Optional list of ticker symbols (e.g., ["AAPL", "MSFT"]). If None, fetches all tickers.
            include_otc: Whether to include OTC securities in the response (default: False).

        Returns:
            A list of dictionaries representing snapshot data for tickers.
            Returns an empty list if an error occurs.
        """
        snapshot = self.client.get_snapshot_all(
            market_type=market_type,
            )

        print(snapshot)

        # crunch some numbers
        for item in snapshot:
            # verify this is an TickerSnapshot
            if isinstance(item, TickerSnapshot):
                # verify this is an Agg
                if isinstance(item.prev_day, Agg):
                    # verify this is a float
                    if isinstance(item.prev_day.open, float) and isinstance(
                        item.prev_day.close, float
                    ):
                        percent_change = (
                            (item.prev_day.close - item.prev_day.open)
                            / item.prev_day.open
                            * 100
                        )
                        print(
                            "{:<15}{:<15}{:<15}{:.2f} %".format(
                                item.ticker,
                                item.prev_day.open,
                                item.prev_day.close,
                                percent_change,
                            )
                        )

        return snapshot

    def get_market_movers(self, direction: str, include_otc: bool = False) -> List[Dict[str, Any]]:
        """
        Get the top market movers (gainers or losers) based on percentage change.

        Args:
            direction: The direction of movement ('gainers' or 'losers').
            include_otc: Whether to include OTC securities (default: False).

        Returns:
            A list of dictionaries representing snapshot data for top movers.
            Returns an empty list if an error occurs or direction is invalid.
        """
        tickers = self.client.get_snapshot_direction(
            market_type='stocks',
            direction=direction,
            include_otc=include_otc,
            )

        # print ticker with % change
        for item in tickers:
            # verify this is a TickerSnapshot
            if isinstance(item, TickerSnapshot):
                # verify this is a float
                if isinstance(item.todays_change_percent, float):
                    "{:<15}{:.2f} %".format(item.ticker, item.todays_change_percent)
        return tickers

    def get_market_status(self) -> Dict[str, Any]:
        """
        Get the current trading status of the overall US market and specific exchanges.

        Returns:
            A dictionary containing the current market status details.
            Returns a dictionary with an error message if fetching fails.
        """
        try:
            status = self.client.get_market_status()

            return status

        except Exception as e:
            print(f"Error fetching market status: {e}")
            return {"error": f"Failed to fetch market status: {str(e)}"}

    def get_stock_financials(
        self,
        ticker: Optional[str] = None,
        timeframe: Optional[str] = 'quarterly', # 'annual', 'quarterly', 'ttm'
    ) -> Dict[str, Any]:
        """
        Get historical financial data for a stock ticker from SEC filings (EXPERIMENTAL API).

        Args:
            ticker: Query by ticker symbol.
            cik: Query by CIK number.
            company_name: Query by company name.
            filing_date: Query by filing date (YYYY-MM-DD).
            period_of_report_date: Query by period of report date (YYYY-MM-DD).
            timeframe: Query by timeframe (annual, quarterly).
            include_sources: Include xpath and formula attributes (default: False).
            limit: Limit the number of results (default: 10, max: 100).
            sort: Sort field for ordering (e.g., filing_date, period_of_report_date).

        Returns:
            A dictionary containing the list of financial results ('results') and potentially a 'next_url'.
            Returns a dictionary with an error message if fetching fails.
        """
        try:
            # Use the client's get_stock_financials method
            response =  self.client.vx.list_stock_financials(
                ticker=ticker,
                timeframe=timeframe,
                order='desc',
                include_sources=False,
                limit=1,
            )

            return list(response)
        except Exception as e:
            print(f"Error fetching stock financials: {e}")
            return {"error": f"Failed to fetch stock financials: {str(e)}"}


def prepare_news_for_llm(news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepare company news data (list of dicts) for an LLM by removing URLs.

    Args:
        news_list: List of dictionaries containing news data (like from get_ticker_news_basic).

    Returns:
        List of dictionaries containing cleaned news data.
    """
    processed_news = []
    for news_item in news_list:
        # Create a copy to avoid modifying original dicts
        cleaned_item = news_item.copy()
        # Remove URL fields
        cleaned_item.pop('article_url', None)
        cleaned_item.pop('image_url', None)
        processed_news.append(cleaned_item)
    return processed_news


def parse_news_by_date(news_list: List[Dict[str, Any]]):
    """
    Parse news (list of dicts) by date and return a dictionary with date as key and news as value.
    """
    news_dict = {}
    for news in news_list:
        try:
            # Parse the ISO timestamp string
            date_str = pd.to_datetime(news.get('published_utc')).strftime('%Y-%m-%d')
            if date_str not in news_dict:
                news_dict[date_str] = []
            news_dict[date_str].append(news)
        except Exception as e:
            print(f"Could not parse date for news item: {news.get('id', 'N/A')}, error: {e}")
            continue # Skip items with unparseable dates

    print(f'{len(news_dict)} days of news parsed')
    return news_dict