import requests
import pandas as pd
import os
import json
from dotenv import load_dotenv
from src.data_tool.data_models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
)
from src.data_tool.data_operations import DataOperations

load_dotenv()

fd_key = os.getenv('FINANCIAL_DATASETS_API_KEY')

if fd_key is None:
    raise ValueError('FINANCIAL_DATASETS_API_KEY is not set')
else:
    print('FINANCIAL_DATASETS_API_KEY is set')

    
    
class FinancialDatasets:
    def __init__(self):
        self.base_url = 'https://api.financialdatasets.ai'
        self.headers = {
            "X-API-KEY": fd_key
        }
        self.data_ops = DataOperations()
        
    def check_and_get_from_db(self, data_type, condition, api_fetch_func, *args, **kwargs):
        """
        Universal function to check if data exists in DB and fetch from API if needed
        
        Args:
            data_type (str): The table name to check in database
            condition (str): SQL WHERE condition to check for existence
            api_fetch_func (callable): Function to call if data not in database
            *args, **kwargs: Arguments to pass to the API fetch function
            
        Returns:
            The requested data, either from database or API, in model format
        """
        # Check if the table exists first
        if not self.data_ops.db.check_if_table_exists(data_type):
            print(f"Table {data_type} does not exist in database, fetching from API")
            api_data = api_fetch_func(*args, **kwargs)
            self._store_api_data(data_type, api_data, *args, **kwargs)
            return api_data
        
        # Different checking logic based on data type
        has_data = False
        
        # Get parameters
        ticker = kwargs.get('ticker', args[0] if args else None)
        limit = kwargs.get('limit', 1000)
        
        try:
            if data_type == 'company_news':
                # For news, check if we have at least one record for each day in the date range
                start_date = kwargs.get('start_date', args[1] if len(args) > 1 else None)
                end_date = kwargs.get('end_date', args[2] if len(args) > 2 else None)
                
                if start_date and end_date:
                    # First, get the count of distinct dates that have news in our range
                    distinct_dates_query = f"""
                        SELECT COUNT(DISTINCT DATE(date)) as date_count,
                               DATEDIFF('{end_date}', '{start_date}') + 1 as total_days
                        FROM {data_type} 
                        WHERE ticker = '{ticker}' 
                        AND date BETWEEN '{start_date}' AND '{end_date}'
                    """
                    result = self.data_ops.db.execute_sql_scalar_tuple(distinct_dates_query)
                    if result:
                        date_count, total_days = result
                        
                        # Also get total records for logging
                        count_query = f"SELECT COUNT(*) FROM {data_type} WHERE ticker = '{ticker}' AND date BETWEEN '{start_date}' AND '{end_date}'"
                        total_records = self.data_ops.db.execute_sql_scalar(count_query)
                        
                        print(f"Found {total_records} news records across {date_count} days (out of {total_days} days) for {ticker} between {start_date} and {end_date}")
                        
                        # We consider we have data if we have at least one record for each day
                        has_data = date_count >= total_days
                        if not has_data:
                            print(f"Missing news for {total_days - date_count} days in the date range")
                    else:
                        has_data = False
            
            elif data_type == 'price':
                # For prices, check if we have data points for the start and end dates
                start_date = kwargs.get('start_date', args[1] if len(args) > 1 else None)
                end_date = kwargs.get('end_date', args[2] if len(args) > 2 else None)
                
                if start_date and end_date:
                    # Count total records in the date range
                    count_query = f"SELECT COUNT(*) FROM {data_type} WHERE ticker = '{ticker}' AND time BETWEEN '{start_date}' AND '{end_date}'"
                    count_result = self.data_ops.db.execute_sql_scalar(count_query)
                    
                    # For price data, we expect data for each trading day
                    has_data = count_result > 0
                    
                    print(f"Found {count_result} price records in database for {ticker} between {start_date} and {end_date}")
                    
            elif data_type == 'financial_metrics':
                # For financial metrics, check if we have the report for the specified period
                end_date = kwargs.get('end_date', args[1] if len(args) > 1 else None)
                period = kwargs.get('period', 'ttm')
                
                if end_date:
                    # Check if we have any metrics for this period
                    check_query = f"SELECT COUNT(*) FROM {data_type} WHERE ticker = '{ticker}' AND report_period <= '{end_date}' AND period = '{period}'"
                    count_result = self.data_ops.db.execute_sql_scalar(check_query)
                    has_data = count_result > 0
                    
                    print(f"Found {count_result} financial metrics records in database for {ticker} for period {period}")
                    
            elif data_type == 'insider_trade':
                # For insider trades, check if we have data in the date range
                end_date = kwargs.get('end_date', args[1] if len(args) > 1 else None)
                start_date = kwargs.get('start_date', args[2] if len(args) > 2 else None)
                
                condition_query = f"ticker = '{ticker}' AND filing_date <= '{end_date}'"
                if start_date:
                    condition_query += f" AND filing_date >= '{start_date}'"
                    
                # Check if we have any insider trades in this period
                check_query = f"SELECT COUNT(*) FROM {data_type} WHERE {condition_query}"
                count_result = self.data_ops.db.execute_sql_scalar(check_query)
                has_data = count_result > 0
                
                print(f"Found {count_result} insider trade records in database for {ticker}")
            
            else:
                # For other data types, use the original check
                has_data = self.data_ops.check_data_exists(data_type, condition)
        except Exception as e:
            print(f"Error checking database for {data_type}: {e}")
            has_data = False
        
        # If we have sufficient data in database
        if has_data:
            print(f"Using data from database for {data_type}")
            # Query the database to get the data
            result_df = self.data_ops.db.read_table_with_condition(data_type, condition, limit=limit)
            
            # Convert DataFrame back to the appropriate Pydantic model
            if data_type == 'price':
                return self._df_to_price_models(result_df)
            elif data_type == 'financial_metrics':
                return self._df_to_financial_metrics_models(result_df)
            elif data_type == 'insider_trade':
                return self._df_to_insider_trade_models(result_df)
            elif data_type == 'company_news':
                return self._df_to_company_news_models(result_df)
            else:
                return result_df
        
        # Data not found or insufficient, fetch from API
        print(f"Data not found in database for {data_type}, fetching from API")
        api_data = api_fetch_func(*args, **kwargs)
        
        # Store the API data
        self._store_api_data(data_type, api_data, *args, **kwargs)
            
        return api_data
    
    def _df_to_price_models(self, df):
        """Convert a DataFrame of price data to a list of Price models"""
        if df.empty:
            return []
        
        price_list = []
        for _, row in df.iterrows():
            price_dict = row.to_dict()
            price_list.append(Price(**price_dict))
        
        return price_list
    
    def _df_to_financial_metrics_models(self, df):
        """Convert a DataFrame of financial metrics to a list of FinancialMetrics models"""
        if df.empty:
            return []
        
        metrics_list = []
        for _, row in df.iterrows():
            metrics_dict = row.to_dict()
            metrics_list.append(FinancialMetrics(**metrics_dict))
        
        return metrics_list
    
    def _df_to_insider_trade_models(self, df):
        """Convert a DataFrame of insider trades to a list of InsiderTrade models"""
        if df.empty:
            return []
        
        trades_list = []
        for _, row in df.iterrows():
            trade_dict = row.to_dict()
            trades_list.append(InsiderTrade(**trade_dict))
        
        return trades_list
    
    def _df_to_company_news_models(self, df):
        """Convert a DataFrame of company news to a list of CompanyNews models"""
        if df.empty:
            return []
        
        news_list = []
        for _, row in df.iterrows():
            news_dict = row.to_dict()
            news_list.append(CompanyNews(**news_dict))
        
        return news_list
    
    def _store_api_data(self, data_type, api_data, *args, **kwargs):
        """Helper method to store API data in the database"""
        ticker = kwargs.get('ticker', args[0] if args else None)
        
        # Store the data in the database based on data_type
        if data_type == 'price' and isinstance(api_data, list) and all(isinstance(item, Price) for item in api_data):
            self.data_ops.insert_price_data(api_data, ticker)
        elif data_type == 'financial_metrics' and isinstance(api_data, list) and all(isinstance(item, FinancialMetrics) for item in api_data):
            self.data_ops.insert_financial_metrics(api_data)
        elif data_type == 'insider_trade' and isinstance(api_data, list) and all(isinstance(item, InsiderTrade) for item in api_data):
            self.data_ops.insert_insider_trades(api_data)
        elif data_type == 'company_news' and isinstance(api_data, list) and all(isinstance(item, CompanyNews) for item in api_data):
            self.data_ops.insert_company_news(api_data)
    
    def get_prices(self, ticker, start_date, end_date):
        """Get price data for a ticker within a date range, checking DB first"""
        condition = f"ticker = '{ticker}' AND time BETWEEN '{start_date}' AND '{end_date}'"
        
        def api_fetch(*args, **kwargs):
            # Extract parameters from kwargs or use defaults from outer scope
            _ticker = kwargs.get('ticker', ticker)
            _start_date = kwargs.get('start_date', start_date)
            _end_date = kwargs.get('end_date', end_date)
            
            url = (
                f'{self.base_url}/prices'
                f'?ticker={_ticker}'
                f'&start_date={_start_date}'
                f'&end_date={_end_date}'
            )
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {_ticker} - {response.status_code} - {response.text}")
            
            data = response.json()
            price_response = PriceResponse(**data)
            return price_response.prices
        
        return self.check_and_get_from_db('price', condition, api_fetch, ticker=ticker, start_date=start_date, end_date=end_date)
    
    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        """Get financial metrics, checking DB first"""
        condition = f"ticker = '{ticker}' AND report_period <= '{end_date}' AND period = '{period}'"
        
        def api_fetch(*args, **kwargs):
            # Extract parameters from kwargs or use defaults from outer scope
            _ticker = kwargs.get('ticker', ticker)
            _end_date = kwargs.get('end_date', end_date)
            _period = kwargs.get('period', period)
            _limit = kwargs.get('limit', limit)
            
            url = (
                f'{self.base_url}/financial-metrics'
                f'?ticker={_ticker}'
                f'&end_date={_end_date}'
                f'&period={_period}'
                f'&limit={_limit}'
            )
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {_ticker} - {response.status_code} - {response.text}")
            
            data = response.json()
            metrics_response = FinancialMetricsResponse(**data)
            return metrics_response.financial_metrics
        
        return self.check_and_get_from_db('financial_metrics', condition, api_fetch, ticker=ticker, end_date=end_date, period=period, limit=limit)
    
    def search_line_items(self, ticker, line_items, end_date, period="ttm", limit=10):
        """Get line items, checking DB first if implemented"""
        # Note: This would need a dedicated table for line items in the database
        url = (
            f'{self.base_url}/financials/search/line-items'
            f'?ticker={ticker}'
            f'&line_items={line_items}'
            f'&end_date={end_date}'
            f'&period={period}'
            f'&limit={limit}'
        )
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
        
        data = response.json()
        line_item_response = LineItemResponse(**data)
        line_items = line_item_response.line_items
        return line_items
    
    def get_insider_trades(self, ticker, end_date, start_date=None, limit=1000):
        """Get insider trades, checking DB first"""
        condition = f"ticker = '{ticker}' AND filing_date <= '{end_date}'"
        if start_date:
            condition += f" AND filing_date >= '{start_date}'"
        
        def api_fetch(*args, **kwargs):
            # Extract parameters from kwargs or use defaults from outer scope
            _ticker = kwargs.get('ticker', ticker)
            _end_date = kwargs.get('end_date', end_date)
            _start_date = kwargs.get('start_date', start_date)
            _limit = kwargs.get('limit', limit)
            
            url = (
                f'{self.base_url}/insider-trades'
                f'?ticker={_ticker}'
                f'&end_date={_end_date}'
            )
            if _start_date:
                url += f'&start_date={_start_date}'
            url += f'&limit={_limit}'
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {_ticker} - {response.status_code} - {response.text}")
            
            data = response.json()
            insider_trade_response = InsiderTradeResponse(**data)
            return insider_trade_response.insider_trades
        
        return self.check_and_get_from_db('insider_trade', condition, api_fetch, ticker=ticker, end_date=end_date, start_date=start_date, limit=limit)
    
    
    def get_press_releases(self, ticker):
        def check_availability(ticker):
            url = (
                f'{self.base_url}/earnings/press-releases/tickers'
            )
            response = requests.get(url, headers=self.headers)
            available_tickers = response.json()['tickers']
            if ticker in available_tickers:
                print(f'{ticker} is available')
                return True
            else:
                print(f'{ticker} is not available')
                print(available_tickers)
                return False
            
        if not check_availability(ticker):
            return None
        
        url = (
            f'{self.base_url}/earnings/press-releases'
            f'?ticker={ticker}'
        )
        response = requests.get(url, headers=self.headers)
        press_releases = response.json().get('press_releases')
        return press_releases
    
    def get_news(self, ticker, start_date=None, end_date=None, limit=1000):
        """Get company news, checking DB first"""
        condition = f"ticker = '{ticker}'"
        if start_date:
            condition += f" AND date >= '{start_date}'"
        if end_date:
            condition += f" AND date <= '{end_date}'"
        
        def api_fetch(*args, **kwargs):
            # Extract parameters from kwargs or use defaults from outer scope
            _ticker = kwargs.get('ticker', ticker)
            _start_date = kwargs.get('start_date', start_date)
            _end_date = kwargs.get('end_date', end_date)
            _limit = kwargs.get('limit', limit)
            
            url = (
                f'{self.base_url}/news'
                f'?ticker={_ticker}'
            )
            if _start_date:
                url += f'&start_date={_start_date}'
            if _end_date:
                url += f'&end_date={_end_date}'
            url += f'&limit={_limit}'
            print(url)
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {_ticker} - {response.status_code} - {response.text}")
            
            data = response.json()
            response_model = CompanyNewsResponse(**data)
            return response_model.news
        
        return self.check_and_get_from_db('company_news', condition, api_fetch, ticker=ticker, start_date=start_date, end_date=end_date, limit=limit)
    
    def get_market_cap(self, ticker, end_date):
        financial_metrics = self.get_financial_metrics(ticker, end_date)
        
        # Handle both DataFrame (from DB) and list of FinancialMetrics (from API)
        if isinstance(financial_metrics, pd.DataFrame) and not financial_metrics.empty:
            market_cap = financial_metrics.iloc[0]['market_cap']
        elif isinstance(financial_metrics, list) and financial_metrics:
            market_cap = financial_metrics[0].market_cap
        else:
            return None

        return market_cap
    
    def prices_to_df(self, prices) -> pd.DataFrame:
        """Convert prices to a DataFrame."""
        # Handle if prices is already a DataFrame (from DB)
        if isinstance(prices, pd.DataFrame):
            df = prices.copy()
            # Ensure expected processing is done
            if "Date" not in df.columns and "time" in df.columns:
                df["Date"] = pd.to_datetime(df["time"])
                df.set_index("Date", inplace=True)
            numeric_cols = ["open", "close", "high", "low", "volume"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df.sort_index(inplace=True)
            return df
        
        # Handle if prices is a list of Price objects (from API)
        df = pd.DataFrame([p.model_dump() if hasattr(p, "model_dump") else p.dict() for p in prices])
        df["Date"] = pd.to_datetime(df["time"])
        df.set_index("Date", inplace=True)
        numeric_cols = ["open", "close", "high", "low", "volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.sort_index(inplace=True)
        return df

    def get_price_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        prices = self.get_prices(ticker, start_date, end_date)
        return self.prices_to_df(prices)
    
    
        
