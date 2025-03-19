import pandas as pd
import requests
import numpy as np
import time
from requests.exceptions import HTTPError
from urllib3.exceptions import MaxRetryError # Import MaxRetryError
from polygon import RESTClient
import os
from dotenv import load_dotenv


load_dotenv()

class polygon:
    def __init__(self):
        self.api_key = os.getenv('POLYGON_API_KEY')
        self.client = RESTClient(api_key=self.api_key)
        
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
        return all_data
    
    
    
    
    