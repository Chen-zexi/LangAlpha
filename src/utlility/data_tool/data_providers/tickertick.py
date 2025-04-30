from datetime import datetime
import requests
import json


class Tickertick:
    def __init__(self):
        self.feed_url = 'https://api.tickertick.com/feed'
        self.tickers_url = 'https://api.tickertick.com/tickers'
        self.rate_limit = 10  # 10 requests per minute limit

    def get_feed(self, query, limit=30, last_id=None):
        url = f"{self.feed_url}?q={query}"
        
        if limit:
            url += f"&n={limit}"
        
        if last_id:
            url += f"&last={last_id}"
            
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return self.convert_timestamp_ms_to_iso(data)
        else:
            return {"error": f"API request failed with status code {response.status_code}"}
        
    def convert_timestamp_ms_to_iso(self, response):
        for story in response['stories']:
            if 'time' in story:
                timestamp_sec = story['time'] / 1000
                story['time'] = datetime.utcfromtimestamp(timestamp_sec).isoformat()
        return response
    
    def get_ticker_news(self, ticker, limit=30):
        """Get news for a specific ticker"""
        query = f"z:{ticker}"
        return self.get_feed(query, limit)
    
    def get_broad_ticker_news(self, ticker, limit=30):
        """Get broader news for a specific ticker"""
        query = f"tt:{ticker}"
        return self.get_feed(query, limit)
    
    
    def get_news_from_source(self, source, limit=30):
        """Get news from a specific source"""
        query = f"s:{source}"
        return self.get_feed(query, limit)
    
    def get_news_for_multiple_tickers(self, tickers, limit=30):
        """Get news for multiple tickers"""
        ticker_terms = [f"tt:{ticker}" for ticker in tickers]
        query = f"(or {' '.join(ticker_terms)})"
        return self.get_feed(query, limit)
    
    def get_curated_news(self, limit=30):
        """Get curated news from top financial/technology sources"""
        query = "T:curated"
        return self.get_feed(query, limit)
    
    def get_entity_news(self, entity, limit=30):
        """Get news about a specific entity"""
        # Replace spaces with underscores as required by the API
        entity = entity.lower().replace(" ", "_")
        query = f"E:{entity}"
        return self.get_feed(query, limit)
    
    def search_tickers(self, query, limit=5):
        """Search for tickers matching the query"""
        url = f"{self.tickers_url}?p={query}&n={limit}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API request failed with status code {response.status_code}"}
