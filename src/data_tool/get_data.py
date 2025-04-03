# This file will be the main file for data collection
import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
import pandas_market_calendars as mcal
import requests
from src.data_tool.connect_wrds import get_fundamentals_quarterly, get_security_daily
from src.data_tool.data_models import FinancialMetrics, FinancialMetricsResponse, RetailActivityResponse, RetailActivity
from src.data_tool.ploygon import polygon

logger = logging.getLogger(__name__)

def market_is_open(date):
    result = mcal.get_calendar("NASDAQ").valid_days(start_date=date, end_date=date)
    return result.empty == False

def get_last_trading_day(date):
    while not market_is_open(date):
        date = date - timedelta(days=1)
    return date

def calculate_financial_metrics(ticker: str, 
                               date: Optional[str] = None,
                               username: Optional[str] = None) -> FinancialMetrics:
    """
    Calculate financial metrics for the specified ticker as of a specific date.
    
    Args:
        ticker: Ticker symbol
        date: The specific date (YYYY-MM-DD) to calculate metrics for. If None, uses current date.
        username: WRDS username
        
    Returns:
        FinancialMetrics object containing calculated financial metrics
    """
    # Use current date if no date provided
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    # Convert string date to datetime if needed
    if isinstance(date, str):
        target_date = datetime.strptime(date, '%Y-%m-%d')
    
    logger.info(f"Starting financial metrics calculation for {ticker} as of {date}")
    
    # Retrieve security data for the specific date
    security_df = get_security_daily([ticker], date, date, username)
    
    # If no security data found for the specific date, try getting the most recent data
    while security_df.empty:
        logger.warning(f"No security data found for {date}, retrieving latest available data")
        date = (date - timedelta(days=1))
        security_df = get_security_daily([ticker], date, date, username)
        
    
    # For fundamentals, we need to get data from a wider range (up to 1 year before the target date)
    # to ensure we have the latest fundamental data
    start_date = (target_date - timedelta(days=365))
    fundamentals_df = get_fundamentals_quarterly([ticker], start_date, date, username)
    
    
    
    # Store previous quarter if we have at least 2 quarters
    ticker_data = fundamentals_df[fundamentals_df['ticker'] == ticker].sort_values('report_date', ascending=False)
    if len(ticker_data) >= 2:
        current_quarter = ticker_data.iloc[0]
        prev_quarter = ticker_data.iloc[1]
    elif len(ticker_data) == 1:
        current_quarter = ticker_data.iloc[0]
    else:
        logger.warning(f"No quarterly data found for {ticker}")
        return None
    
    # Get latest security data
    security_data = security_df[security_df['ticker'] == ticker].sort_values('datadate', ascending=False)
    if security_data.empty:
        logger.warning(f"No security data found for {ticker}")
        return None
    
    latest_security = security_data.iloc[0].to_dict()
    
    # Create the metric object
    period = f"Q{current_quarter.get('fiscal_quarter', '?')} {current_quarter.get('fiscal_year', '?')}"
    metric = FinancialMetrics(
        ticker=ticker,
        report_period=current_quarter['report_date'].strftime('%Y-%m-%d'),
        period=period,
        currency='USD'
    )
    
    try:
        # Calculate market cap
        metric.market_cap = float(security_data['close_price']) * float(security_data['outstanding_shares'])/1000000
        
        # Calculate earnings growth using previous quarter
        calculate_earnings_growth_from_stored_quarters(metric, current_quarter, prev_quarter) if prev_quarter['basic_eps'] is not None else None
        
        # Profitability metrics
        calculate_profitability_metrics(metric, current_quarter)
        
        # Financial health metrics
        calculate_financial_health_metrics(metric, current_quarter)
        
        # Share structure
        calculate_share_structure_metrics(metric, current_quarter, latest_security)
        
        # Cash flow metrics
        calculate_cash_flow_metrics(metric, current_quarter)
        
        logger.info(f"Successfully calculated metrics for {ticker}")
        return metric
        
    except Exception as e:
        logger.error(f"Error calculating metrics for {ticker}: {str(e)}")
        return None


def calculate_financial_metrics_batch(tickers: List[str], 
                                     date: Optional[str] = None,
                                     username: Optional[str] = None) -> FinancialMetricsResponse:
    """
    Calculate financial metrics for multiple tickers (batch mode).
    
    Args:
        tickers: List of ticker symbols
        date: The specific date (YYYY-MM-DD) to calculate metrics for
        username: WRDS username
        
    Returns:
        FinancialMetricsResponse containing metrics for all tickers
    """
    metrics_list = []
    
    for ticker in tickers:
        metric = calculate_financial_metrics(ticker, date, username)
        if metric:
            metrics_list.append(metric)
    
    return FinancialMetricsResponse(financial_metrics=metrics_list)


def calculate_earnings_growth_from_stored_quarters(metric: FinancialMetrics, current: pd.Series, previous: pd.Series) -> None:
    """Calculate earnings growth between two quarterly periods using stored data."""
    metric.earnings_growth = (float(current['basic_eps']) - float(previous['basic_eps'])) / abs(float(previous['basic_eps']))


def calculate_profitability_metrics(metric: FinancialMetrics, row: pd.Series) -> None:
    """Calculate profitability metrics."""

    metric.return_on_equity = float(row['net_income']) / float(row['common_equity'])
    

    metric.return_on_invested_capital = float(row['net_income']) / float(row['invested_capital'])
    

    metric.operating_margin = float(row['operating_income']) / float(row['revenue'])
    

    gross_profit = float(row['revenue']) - float(row['cost_of_goods_sold'])
    metric.gross_margin = gross_profit / float(row['revenue'])
    

    metric.basic_eps = float(row['basic_eps'])
    metric.earnings_per_share = float(row['basic_eps'])  # Also set the general field
    

    metric.diluted_eps = float(row['diluted_eps'])
    

    metric.revenue = float(row['revenue'])

    metric.net_income = float(row['net_income'])


def calculate_financial_health_metrics(metric: FinancialMetrics, row: pd.Series) -> None:
    """Calculate financial health metrics."""

    metric.debt_to_equity = float(row['long_term_debt']) / float(row['common_equity'])
    metric.current_ratio = float(row['current_assets']) / float(row['current_liabilities'])
    
    # Balance sheet items
    metric.current_assets = float(row.get('current_assets'))
    metric.current_liabilities = float(row.get('current_liabilities'))
    metric.total_assets = float(row.get('total_assets'))
    metric.total_liabilities = float(row.get('total_liabilities'))


def calculate_share_structure_metrics(metric: FinancialMetrics, row: pd.Series, security_data: dict) -> None:
    """Calculate share structure metrics."""
    metric.book_value_per_share = float(row['common_equity']) / float(row['common_shares_outstanding'])
    
    # Outstanding Shares - prefer from fundamentals, fallback to security data
    metric.outstanding_shares = float(row.get('common_shares_outstanding', security_data.get('outstanding_shares')  ))
    
    # Dividend information - ensure values are set even if not in security data
    # Check if keys exist in security_data, otherwise use defaults
    try:
        metric.dividends = 0.0
        metric.special_distributions = 0.0
        
        if 'dividends' in security_data and security_data['dividends'] is not None:
            metric.dividends = float(security_data['dividends'])
        
        if 'special_distributions' in security_data and security_data['special_distributions'] is not None:
            metric.special_distributions = float(security_data['special_distributions'])
    except Exception as e:
        logger.warning(f"Error setting dividend values: {str(e)}")
        metric.dividends = 0.0
        metric.special_distributions = 0.0


def calculate_cash_flow_metrics(metric: FinancialMetrics, row: pd.Series) -> None:
    """Calculate cash flow metrics."""
    # Cash flow metrics
    metric.operating_cash_flow = float(row.get('net_operating_cash_flow'))
    metric.capital_expenditure = float(row.get('capital_expenditure'))
        
    # Calculate free cash flow even if one component is missing
    if metric.operating_cash_flow and metric.capital_expenditure:
        metric.free_cash_flow = float(metric.operating_cash_flow) - float(metric.capital_expenditure)
    if not metric.operating_cash_flow:
        logger.warning(f"No operating cash flow data for {metric.ticker}")
    if not metric.capital_expenditure:
        logger.warning(f"No capital expenditure data for {metric.ticker}")
        
    if metric.free_cash_flow:
        metric.fcf_yield = float(metric.free_cash_flow) / float(metric.market_cap)


def get_retail_activity(ticker: str, date: str) -> pd.DataFrame:
    """Get retail trades for a specific ticker and date."""
    NASDAQ_API_KEY = os.getenv('NASDAQ_API_KEY')
    date = datetime.strptime(date, '%Y-%m-%d')
    count = 0
    dates = []
    while count < 7:
        date = get_last_trading_day(date)
        count += 1
        dates.append(date.strftime('%Y-%m-%d'))
        date = date - timedelta(days=1)
        
        
    dates = '%2c'.join(dates)    
    url = f'https://data.nasdaq.com/api/v3/datatables/NDAQ/RTAT10?date={dates}&ticker={ticker}&api_key={NASDAQ_API_KEY}'
    response = requests.get(url)
    response = response.json()['datatable']['data']
    retail_activity = []
    for row in response:
        activity = RetailActivity(
            ticker=row[0],
            date=row[1],
            activity=row[2],
            sentiment=row[3]
        )
        retail_activity.append(activity)
    return RetailActivityResponse(results=retail_activity)



# News - Polygon
def get_news(ticker: str, date: str) -> pd.DataFrame:
    """Get news for a specific ticker and date."""
    polygon = polygon()
    return polygon.get_news(ticker, date)