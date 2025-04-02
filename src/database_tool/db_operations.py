from src.database_tool.connect_db import ConnectDB
import pandas as pd
from src.data_tool.data_models import Price, FinancialMetrics, LineItem, InsiderTrade, CompanyNews, Position, Portfolio, AnalystSignal, TickerAnalysis, AgentStateData
from sqlalchemy import text

class DataOperations:
    def __init__(self):
        # Create a single instance of ConnectDB to use across the class
        self.db = ConnectDB()
        self.engine = self.db.get_engine()
    
    @staticmethod
    def model_to_dict(model_instance):
        """Convert a Pydantic model instance to a dictionary suitable for database insertion"""
        if hasattr(model_instance, "model_dump"):
            return model_instance.model_dump()
        else:
            return model_instance.dict()
    
    def check_data_exists(self, table, condition):
        """
        Check if data exists in the specified table that matches the condition
        
        Args:
            table (str): The table name to check
            condition (str): SQL WHERE condition, e.g. "ticker = 'AAPL' AND time = '2023-01-01'"
            
        Returns:
            bool: True if matching data exists, False otherwise
        """
        sql = text(f"SELECT 1 FROM {table} WHERE {condition} LIMIT 1")
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return result.fetchone() is not None
    
    def insert_price_data(self, prices, ticker, check_duplicates=True):
        """
        Insert price data into the database
        
        Args:
            prices (list[Price]): List of Price objects
            ticker (str): The ticker symbol
            check_duplicates (bool): Whether to check for and skip duplicate entries
        """
        price_data = []
        
        for price in prices:
            # Skip if this price data already exists
            if check_duplicates:
                condition = f"ticker = '{ticker}' AND time = '{price.time}'"
                if self.check_data_exists('price', condition):
                    print(f"Price data for {ticker} at {price.time} already exists, skipping")
                    continue
            
            price_dict = self.model_to_dict(price)
            price_dict['ticker'] = ticker
            price_data.append(price_dict)
        
        if price_data:
            df = pd.DataFrame(price_data)
            self.db.insert_df_to_table('price', df)
            print(f"Inserted {len(price_data)} price records for {ticker}")
        else:
            print(f"No new price data to insert for {ticker}")
    
    def insert_financial_metrics(self, metrics, check_duplicates=True):
        """
        Insert financial metrics into the database
        
        Args:
            metrics (list[FinancialMetrics]): List of FinancialMetrics objects
            check_duplicates (bool): Whether to check for and skip duplicate entries
        """
        metrics_data = []
        
        for metric in metrics:
            # Skip if this metric already exists
            if check_duplicates:
                condition = f"ticker = '{metric.ticker}' AND report_period = '{metric.report_period}' AND period = '{metric.period}'"
                if self.check_data_exists('financial_metrics', condition):
                    print(f"Financial metrics for {metric.ticker} for {metric.report_period} ({metric.period}) already exists, skipping")
                    continue
                    
            metrics_data.append(self.model_to_dict(metric))
        
        if metrics_data:
            df = pd.DataFrame(metrics_data)
            self.db.insert_df_to_table('financial_metrics', df)
            print(f"Inserted {len(metrics_data)} financial metrics records")
        else:
            print("No new financial metrics to insert")
    
    def insert_insider_trades(self, trades, check_duplicates=True):
        """
        Insert insider trades into the database
        
        Args:
            trades (list[InsiderTrade]): List of InsiderTrade objects
            check_duplicates (bool): Whether to check for and skip duplicate entries
        """
        trades_data = []
        
        for trade in trades:
            # Skip if this trade already exists
            if check_duplicates:
                condition = f"ticker = '{trade.ticker}' AND filing_date = '{trade.filing_date}'"
                if trade.name:
                    condition += f" AND name = '{trade.name}'"
                if trade.transaction_date:
                    condition += f" AND transaction_date = '{trade.transaction_date}'"
                    
                if self.check_data_exists('insider_trade', condition):
                    print(f"Insider trade for {trade.ticker} on {trade.filing_date} already exists, skipping")
                    continue
                    
            trades_data.append(self.model_to_dict(trade))
        
        if trades_data:
            df = pd.DataFrame(trades_data)
            self.db.insert_df_to_table('insider_trade', df)
            print(f"Inserted {len(trades_data)} insider trade records")
        else:
            print("No new insider trades to insert")
    
    def insert_company_news(self, news_items, check_duplicates=True):
        """
        Insert company news into the database
        
        Args:
            news_items (list[CompanyNews]): List of CompanyNews objects
            check_duplicates (bool): Whether to check for and skip duplicate entries
        """
        news_data = []
        
        for news in news_items:
            # Skip if this news already exists
            if check_duplicates:
                # Using URL as a unique identifier
                condition = f"url = '{news.url}'"
                if self.check_data_exists('company_news', condition):
                    print(f"News article with URL {news.url} already exists, skipping")
                    continue
                    
            news_data.append(self.model_to_dict(news))
        
        if news_data:
            df = pd.DataFrame(news_data)
            self.db.insert_df_to_table('company_news', df)
            print(f"Inserted {len(news_data)} company news records")
        else:
            print("No new company news to insert")
    
    def insert_analyst_signals(self, ticker, ticker_analysis, check_duplicates=False):
        """
        Insert analyst signals into the database
        
        Args:
            ticker (str): The ticker symbol
            ticker_analysis (TickerAnalysis): TickerAnalysis object containing analyst signals
            check_duplicates (bool): Whether to check for and skip duplicate entries
        """
        signals_data = []
        
        for agent_name, signal in ticker_analysis.analyst_signals.items():
            # For analyst signals, we usually want to update rather than check for duplicates,
            # but we provide the option
            if check_duplicates:
                condition = f"ticker = '{ticker}' AND agent_name = '{agent_name}'"
                if self.check_data_exists('analyst_signal', condition):
                    print(f"Analyst signal for {ticker} from {agent_name} already exists, skipping")
                    continue
                    
            signal_dict = self.model_to_dict(signal)
            signal_dict['agent_name'] = agent_name
            signal_dict['ticker'] = ticker
            
            # Handle reasoning which could be a dict or string
            if isinstance(signal_dict.get('reasoning', None), dict):
                signal_dict['reasoning'] = str(signal_dict['reasoning'])
            
            signals_data.append(signal_dict)
        
        if signals_data:
            df = pd.DataFrame(signals_data)
            self.db.insert_df_to_table('analyst_signal', df)
            print(f"Inserted {len(signals_data)} analyst signal records for {ticker}")
        else:
            print(f"No new analyst signals to insert for {ticker}")
    
    def get_latest_prices(self, ticker, limit=10):
        """
        Get the latest price data for a given ticker
        
        Args:
            ticker (str): The ticker symbol
            limit (int): Maximum number of price points to return
            
        Returns:
            pd.DataFrame: DataFrame containing the price data
        """
        sql = text(f"SELECT * FROM price WHERE ticker = '{ticker}' ORDER BY time DESC LIMIT {limit}")
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def get_latest_financial_metrics(self, ticker, period_type=None):
        """
        Get the latest financial metrics for a given ticker
        
        Args:
            ticker (str): The ticker symbol
            period_type (str, optional): Filter by period type ('annual', 'quarterly', etc.)
            
        Returns:
            pd.DataFrame: DataFrame containing the financial metrics
        """
        condition = f"ticker = '{ticker}'"
        if period_type:
            condition += f" AND period = '{period_type}'"
            
        sql = text(f"SELECT * FROM financial_metrics WHERE {condition} ORDER BY report_period DESC LIMIT 1")
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def get_recent_insider_trades(self, ticker, limit=10):
        """
        Get recent insider trades for a given ticker
        
        Args:
            ticker (str): The ticker symbol
            limit (int): Maximum number of trades to return
            
        Returns:
            pd.DataFrame: DataFrame containing the insider trades
        """
        sql = text(f"SELECT * FROM insider_trade WHERE ticker = '{ticker}' ORDER BY filing_date DESC LIMIT {limit}")
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def get_recent_news(self, ticker, limit=10):
        """
        Get recent news for a given ticker
        
        Args:
            ticker (str): The ticker symbol
            limit (int): Maximum number of news items to return
            
        Returns:
            pd.DataFrame: DataFrame containing the news items
        """
        sql = text(f"SELECT * FROM company_news WHERE ticker = '{ticker}' ORDER BY date DESC LIMIT {limit}")
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    
    def get_analyst_signals(self, ticker=None, agent_name=None):
        """
        Get analyst signals, optionally filtered by ticker and/or agent
        
        Args:
            ticker (str, optional): Filter by ticker symbol
            agent_name (str, optional): Filter by agent name
            
        Returns:
            pd.DataFrame: DataFrame containing the analyst signals
        """
        conditions = []
        if ticker:
            conditions.append(f"ticker = '{ticker}'")
        if agent_name:
            conditions.append(f"agent_name = '{agent_name}'")
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = text(f"SELECT * FROM analyst_signal WHERE {where_clause}")
        
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return pd.DataFrame(result.fetchall(), columns=result.keys()) 