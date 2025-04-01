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
    def get_prices(self, ticker, start_date, end_date):
        url = (
            f'{self.base_url}/prices'
            f'?ticker={ticker}'
            f'&start_date={start_date}'
            f'&end_date={end_date}'
        )
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
        
        data = response.json()
        price_response = PriceResponse(**data)
        prices = price_response.prices
        return prices
    
    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        url = (
            f'{self.base_url}/financial-metrics'
            f'?ticker={ticker}'
            f'&end_date={end_date}'
            f'&period={period}'
            f'&limit={limit}'
        )
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
        
        data = response.json()
        metrics_response = FinancialMetricsResponse(**data)
        financial_metrics = metrics_response.financial_metrics
        return financial_metrics
    
    def search_line_items(self, ticker, line_items, end_date, period="ttm", limit=10):
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
        url = (
            f'{self.base_url}/insider-trades'
            f'?ticker={ticker}'
            f'&end_date={end_date}'
        )
        if start_date:
            url += f'&start_date={start_date}'
        url += f'&limit={limit}'
        
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
        
        data = response.json()
        insider_trade_response = InsiderTradeResponse(**data)
        insider_trades = insider_trade_response.insider_trades  
        return insider_trades
    
    
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
    
    def get_news(self, ticker, start_date, end_date, limit=1000):
        
        url = (
            f'{self.base_url}/news'
            f'?ticker={ticker}'
            f'&end_date={end_date}'
        )
        if start_date:
            url += f'&start_date={start_date}'
        url += f'&limit={limit}'
        
        all_news = []
        
        response = requests.get(url, headers=self.headers)
        news = response.json().get('news')
        
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
        
        data = response.json()
        response_model = CompanyNewsResponse(**data)
        company_news = response_model.news
        
            
        all_news.extend(company_news)
        return all_news
    
    def get_market_cap(self, ticker, end_date):
        financial_metrics = self.get_financial_metrics(ticker, end_date)
        market_cap = financial_metrics[0].market_cap
        if not market_cap:
            return None

        return market_cap
    
    def prices_to_df(self, prices: list[Price]) -> pd.DataFrame:
        """Convert prices to a DataFrame."""
        df = pd.DataFrame([p.model_dump() for p in prices])
        df["Date"] = pd.to_datetime(df["time"])
        df.set_index("Date", inplace=True)
        numeric_cols = ["open", "close", "high", "low", "volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.sort_index(inplace=True)
        return df


# Update the get_price_data function to use the new functions
    def get_price_data(self,ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        prices = self.get_prices(ticker, start_date, end_date)
        return self.prices_to_df(prices)
    
    
        
