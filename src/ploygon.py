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


load_dotenv()

class polygon:
    def __init__(self):
        self.api_key = os.getenv('POLYGON_API_KEY')
        if self.api_key is None:
            raise ValueError("POLYGON_API_KEY is not set")
        else:
            print("POLYGON_API_KEY is set")
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
    
    def get_news(self, ticker, from_date, to_date, order="asc", limit=100):
        """
        Get news for a ticker or tickers.
        
        Args:
            ticker: A ticker symbol or list of ticker symbols
            from_date: Start date in format YYYY-MM-DD
            to_date: End date in format YYYY-MM-DD
            order: Order of results, "asc" or "desc"
            limit: Maximum number of results to return
            
        Returns:
            Tuple containing (news_data, news_df) where:
            - news_data is the full response dictionary
            - news_df is a DataFrame with key information
        """
        # Get news data
        news_list = []
        api_response = self.client.list_ticker_news(
            ticker=ticker,
            published_utc_gte=from_date,
            published_utc_lte=to_date,
            order=order,
            limit=limit,
            sort="published_utc",
        )
        
        # Convert API response objects to dictionaries
        for n in api_response:
            # Convert the response object to JSON string then to dict
            news_json = json.loads(json.dumps(n, default=lambda o: o.__dict__))
            news_list.append(news_json)
        
        # Create a response dictionary similar to the sample
        news_data = {
            "count": len(news_list),
            "results": news_list,
        }
        
        # Extract key information for DataFrame
        news_items = []
        for item in news_list:
            # Process publisher data if it exists
            publisher_name = None
            if 'publisher' in item and item['publisher'] is not None:
                if isinstance(item['publisher'], dict) and 'name' in item['publisher']:
                    publisher_name = item['publisher']['name']
            
            # Process insights data to extract specific fields
            sentiment = None
            sentiment_reasoning = None
            insight_tickers = None
            
            if item.get('insights') and isinstance(item.get('insights'), list) and len(item.get('insights')) > 0:
                insight = item.get('insights')[0]  # Get first insight
                sentiment = insight.get('sentiment')
                sentiment_reasoning = insight.get('sentiment_reasoning')
                insight_tickers = insight.get('ticker')  # Note: This is renamed from "ticker" in the insights
                    
            news_dict = {
                'id': item.get('id'),
                'title': item.get('title'),
                'publisher_name': publisher_name,
                'author': item.get('author'),
                'description': item.get('description'),
                'article_url': item.get('article_url'),
                'published_utc': item.get('published_utc'),
                'tickers': item.get('tickers'),
                'keywords': item.get('keywords'),
                'sentiment': sentiment,
                'sentiment_reasoning': sentiment_reasoning,
                'insight_tickers': insight_tickers
            }
            news_items.append(news_dict)
        
        # Create DataFrame
        if news_items:
            news_df = pd.DataFrame(news_items)
            
            # Convert UTC to EST (UTC-5/UTC-4 during DST)
            if 'published_utc' in news_df.columns and not news_df.empty and news_df['published_utc'].notna().any():
                news_df['published_utc'] = pd.to_datetime(news_df['published_utc'])
                # Check if already timezone aware
                if news_df['published_utc'].dt.tz is None:
                    news_df['published_est'] = news_df['published_utc'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
                else:
                    # Already timezone aware, just convert
                    news_df['published_est'] = news_df['published_utc'].dt.tz_convert('US/Eastern')
            
            return news_data, news_df
        else:
            return news_data, pd.DataFrame()
    
    sample_news = {
    "count": 1,
    "next_url": "https://api.polygon.io:443/v2/reference/news?cursor=eyJsaW1pdCI6MSwic29ydCI6InB1Ymxpc2hlZF91dGMiLCJvcmRlciI6ImFzY2VuZGluZyIsInRpY2tlciI6e30sInB1Ymxpc2hlZF91dGMiOnsiZ3RlIjoiMjAyMS0wNC0yNiJ9LCJzZWFyY2hfYWZ0ZXIiOlsxNjE5NDA0Mzk3MDAwLG51bGxdfQ",
    "request_id": "831afdb0b8078549fed053476984947a",
    "results": [
        {
        "amp_url": "https://m.uk.investing.com/news/stock-market-news/markets-are-underestimating-fed-cuts-ubs-3559968?ampMode=1",
        "article_url": "https://uk.investing.com/news/stock-market-news/markets-are-underestimating-fed-cuts-ubs-3559968",
        "author": "Sam Boughedda",
        "description": "UBS analysts warn that markets are underestimating the extent of future interest rate cuts by the Federal Reserve, as the weakening economy is likely to justify more cuts than currently anticipated.",
        "id": "8ec638777ca03b553ae516761c2a22ba2fdd2f37befae3ab6fdab74e9e5193eb",
        "image_url": "https://i-invdn-com.investing.com/news/LYNXNPEC4I0AL_L.jpg",
        "insights": [
            {
            "sentiment": "positive",
            "sentiment_reasoning": "UBS analysts are providing a bullish outlook on the extent of future Federal Reserve rate cuts, suggesting that markets are underestimating the number of cuts that will occur.",
            "ticker": "UBS"
            }
        ],
        "keywords": [
            "Federal Reserve",
            "interest rates",
            "economic data"
        ],
        "published_utc": "2024-06-24T18:33:53Z",
        "publisher": {
            "favicon_url": "https://s3.polygon.io/public/assets/news/favicons/investing.ico",
            "homepage_url": "https://www.investing.com/",
            "logo_url": "https://s3.polygon.io/public/assets/news/logos/investing.png",
            "name": "Investing.com"
        },
        "tickers": [
            "UBS"
        ],
        "title": "Markets are underestimating Fed cuts: UBS By Investing.com - Investing.com UK"
        }
    ],
    "status": "OK"
    }

    
    