import pandas as pd
import requests
import numpy as np
import time
import json
from requests.exceptions import HTTPError
from urllib3.exceptions import MaxRetryError # Import MaxRetryError
from polygon import RESTClient
from polygon.rest.models import (
    TickerNews,
)
import os
from dotenv import load_dotenv
from src.data_tool.data_models import (
    insights,
    CompanyNews,
    CompanyNewsResponse,
)
from src.database_tool.db_operations import DataOperations # Added import


load_dotenv()

class polygon:
    def __init__(self):
        self.api_key = os.getenv('POLYGON_API_KEY')
        if self.api_key is None:
            raise ValueError("POLYGON_API_KEY is not set")
        else:
            print("POLYGON_API_KEY is set")
        self.client = RESTClient(api_key=self.api_key)
        self.db_ops = DataOperations() # Instantiate DataOperations
        
    def get_data(self, ticker, multiplier=1, timespan='day', from_date='2025-03-13', to_date='2025-03-17', limit=100000):
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

