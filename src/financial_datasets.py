import requests
import os
import json
from dotenv import load_dotenv

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
        
    def get_company_facts(self, ticker):
        url = f'{self.base_url}/company/facts'
        params = {
            'ticker': ticker
        }
        response = requests.get(url, headers=self.headers, params=params)
        facts = response.json()
        return facts
    
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
