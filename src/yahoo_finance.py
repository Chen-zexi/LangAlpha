import os
from dotenv import load_dotenv
from requests_oauthlib import OAuth1
import requests
from yahooquery import Ticker
import pandas as pd

load_dotenv()
class yahoo_finance:
    def __init__(self):
        self.consumer_key = os.getenv('YAHOO_CONSUMER_KEY')
        self.consumer_secret = os.getenv('YAHOO_CONSUMER_SECRET')
        self.app_id = os.getenv('YAHOO_APP_ID')
        self.auth = OAuth1(self.consumer_key, self.consumer_secret)
        if self.consumer_key is None or self.consumer_secret is None:
            raise ValueError("YAHOO_CONSUMER_KEY or YAHOO_CONSUMER_SECRET is not set")
        else:
            print("YAHOO_CONSUMER_KEY and YAHOO_CONSUMER_SECRET are set")
        if self.app_id is None:
            raise ValueError("YAHOO_APP_ID is not set")
        else:
            print("YAHOO_APP_ID is set")

    def get_data(self, ticker, start_date, end_date, interval='1d'):
        ticker = Ticker(ticker)
        return ticker.history(start=start_date, end=end_date, interval=interval)
    
    def get_valuation_metrics(self, tickers):
        stocks = Ticker(tickers)
        stats = stocks.key_stats
        
        data_list = []
        
        for ticker in tickers:
            stat = stats.get(ticker, {})  # Get stats for the ticker or an empty dict
            
            if isinstance(stat, str):  # If the API returns an error message
                print(f"Error fetching data for {ticker}: {stat}")
                continue
            
            data = {
                "Ticker": ticker,
                "Price/Book": stat.get("priceToBook", "N/A"),
                "EV/EBITDA": stat.get("enterpriseToEbitda", "N/A"),
            }
            data_list.append(data)
                
        return pd.DataFrame(data_list)