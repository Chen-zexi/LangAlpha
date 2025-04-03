# This file will be the main file for data collection
import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union

from src.data_tool.connect_wrds import get_fundamentals_quarterly, get_security_daily
from src.data_tool.data_models import FinancialMetrics, FinancialMetricsResponse

logger = logging.getLogger(__name__)

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
    
    logger.info(f"Retrieved fundamentals data: {len(fundamentals_df)} rows")
    logger.info(f"Retrieved security data: {len(security_df)} rows")
    
    
    
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
        calculate_market_cap(metric, latest_security)
        
        # Calculate earnings growth using previous quarter
        if prev_quarter is not None:
            calculate_earnings_growth_from_stored_quarters(metric, current_quarter, prev_quarter)
        
        # Profitability metrics
        calculate_profitability_metrics(metric, current_quarter)
        
        # Financial health metrics
        calculate_financial_health_metrics(metric, current_quarter)
        
        # Share structure
        calculate_share_structure_metrics(metric, current_quarter, latest_security)
        
        # Cash flow metrics
        calculate_cash_flow_metrics(metric, current_quarter)
        
        # Calculate FCF yield if market cap exists
        if metric.free_cash_flow is not None and metric.market_cap and metric.market_cap > 0:
            metric.fcf_yield = metric.free_cash_flow / metric.market_cap
        
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
    if 'basic_eps' in current and current['basic_eps'] and 'basic_eps' in previous and previous['basic_eps']:
        if previous['basic_eps'] != 0:
            metric.earnings_growth = (current['basic_eps'] - previous['basic_eps']) / abs(previous['basic_eps'])
            logger.info(f"Calculated earnings growth for {metric.ticker}: {metric.earnings_growth} " +
                       f"({current['basic_eps']} vs {previous['basic_eps']})")



def calculate_market_cap(metric: FinancialMetrics, security_data: dict) -> None:
    """Calculate market cap from security data."""
    if all(k in security_data for k in ['close_price', 'outstanding_shares']):
        if security_data['outstanding_shares'] and security_data['close_price']:
            metric.market_cap = security_data['close_price'] * security_data['outstanding_shares']


def calculate_profitability_metrics(metric: FinancialMetrics, row: pd.Series) -> None:
    """Calculate profitability metrics."""
    # Return on Equity
    if all(k in row for k in ['net_income', 'common_equity']) and row['common_equity'] and row['common_equity'] != 0:
        metric.return_on_equity = row['net_income'] / row['common_equity']
    
    # Return on Invested Capital
    if all(k in row for k in ['net_income', 'invested_capital']) and row['invested_capital'] and row['invested_capital'] != 0:
        metric.return_on_invested_capital = row['net_income'] / row['invested_capital']
    
    # Operating Margin
    if all(k in row for k in ['operating_income', 'revenue']) and row['revenue'] and row['revenue'] != 0:
        metric.operating_margin = row['operating_income'] / row['revenue']
    
    # Gross Margin
    if all(k in row for k in ['revenue', 'cost_of_goods_sold']) and row['revenue'] and row['revenue'] != 0:
        gross_profit = row['revenue'] - row['cost_of_goods_sold']
        metric.gross_margin = gross_profit / row['revenue']
    
    # EPS metrics
    if 'basic_eps' in row:
        metric.basic_eps = row['basic_eps']
        metric.earnings_per_share = row['basic_eps']  # Also set the general field
    
    if 'diluted_eps' in row:
        metric.diluted_eps = row['diluted_eps']
    
    # Revenue and income
    if 'revenue' in row:
        metric.revenue = row['revenue']
    
    if 'net_income' in row:
        metric.net_income = row['net_income']


def calculate_financial_health_metrics(metric: FinancialMetrics, row: pd.Series) -> None:
    """Calculate financial health metrics."""
    # Debt to Equity
    if all(k in row for k in ['long_term_debt', 'common_equity']) and row['common_equity'] and row['common_equity'] != 0:
        metric.debt_to_equity = row['long_term_debt'] / row['common_equity']
    
    # Current Ratio
    if all(k in row for k in ['current_assets', 'current_liabilities']) and row['current_liabilities'] and row['current_liabilities'] != 0:
        metric.current_ratio = row['current_assets'] / row['current_liabilities']
    
    # Balance sheet items
    metric.current_assets = row.get('current_assets')
    metric.current_liabilities = row.get('current_liabilities')
    metric.total_assets = row.get('total_assets')
    metric.total_liabilities = row.get('total_liabilities')


def calculate_share_structure_metrics(metric: FinancialMetrics, row: pd.Series, security_data: dict) -> None:
    """Calculate share structure metrics."""
    # Book Value per Share
    if all(k in row for k in ['common_equity', 'common_shares_outstanding']) and row['common_shares_outstanding'] and row['common_shares_outstanding'] != 0:
        metric.book_value_per_share = row['common_equity'] / row['common_shares_outstanding']
    
    # Outstanding Shares - prefer from fundamentals, fallback to security data
    metric.outstanding_shares = row.get('common_shares_outstanding', security_data.get('outstanding_shares'))
    
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
    metric.operating_cash_flow = row.get('net_operating_cash_flow')
    metric.capital_expenditure = row.get('capital_expenditure')
        
    # Calculate free cash flow even if one component is missing
    if metric.operating_cash_flow and metric.capital_expenditure:
        metric.free_cash_flow = metric.operating_cash_flow - metric.capital_expenditure
    if not metric.operating_cash_flow:
        logger.warning(f"No operating cash flow data for {metric.ticker}")
    if not metric.capital_expenditure:
        logger.warning(f"No capital expenditure data for {metric.ticker}")



# News - Polygon