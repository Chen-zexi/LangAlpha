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

    def get_data(self, ticker, start_date, end_date, interval='1d'):
        ticker = Ticker(ticker)
        return ticker.history(start=start_date, end=end_date, interval=interval)
