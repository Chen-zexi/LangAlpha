#!/usr/bin/env python3
"""
Test script for financial metrics calculation.
"""
import logging
import sys
from datetime import datetime, timedelta
from src.data_tool.get_data import calculate_financial_metrics, calculate_financial_metrics_batch

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_metrics")

def main():
    # Default parameters
    ticker = 'AAPL'  # Testing with Apple
    
    # Get metrics as of a specific date (default to today)
    target_date = datetime.now().strftime('%Y-%m-%d')
    
    # Check if a date is provided as command line argument
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    
    # Check if a ticker is provided as second command line argument
    if len(sys.argv) > 2:
        ticker = sys.argv[2]
    
    logger.info(f"Testing financial metrics calculation for {ticker}")
    logger.info(f"Target date: {target_date}")
    
    # Call the metrics calculation function for a single ticker
    metric = calculate_financial_metrics(ticker, target_date)
    
    # Print results
    if metric:
        logger.info(f"Success! Retrieved metrics for {ticker}")
        logger.info(f"\nMetrics for {metric.ticker}:")
        logger.info(f"  Period: {metric.period}")
        logger.info(f"  Report date: {metric.report_period}")
        logger.info(f"  Currency: {metric.currency}")
        logger.info(f"  Market cap: {metric.market_cap}")
        logger.info(f"  Earnings growth: {metric.earnings_growth}")
        logger.info(f"  FCF yield: {metric.fcf_yield}")
        logger.info(f"  EPS: {metric.earnings_per_share}")
        logger.info(f"  Revenue: {metric.revenue}")
        logger.info(f"  Free cash flow: {metric.free_cash_flow}")
        logger.info(f"  Operating cash flow: {metric.operating_cash_flow}")
        logger.info(f"  Capital expenditure: {metric.capital_expenditure}")
        logger.info(f"  Dividends: {metric.dividends}")
        logger.info(f"  Special distributions: {metric.special_distributions}")
    else:
        logger.warning("No metrics retrieved")
        
    # Test batch mode with a few tickers
    if len(sys.argv) <= 2:  # Only run this if no specific ticker was requested
        logger.info("\nTesting batch mode with multiple tickers")
        batch_tickers = ['AAPL', 'MSFT', 'GOOGL']
        batch_results = calculate_financial_metrics_batch(batch_tickers, target_date)
        
        if batch_results and batch_results.financial_metrics:
            logger.info(f"Batch mode retrieved {len(batch_results.financial_metrics)} metrics")
            for batch_metric in batch_results.financial_metrics:
                logger.info(f"  - {batch_metric.ticker}: {batch_metric.period}, EPS: {batch_metric.earnings_per_share}")
        else:
            logger.warning("No metrics retrieved in batch mode")

if __name__ == "__main__":
    main() 