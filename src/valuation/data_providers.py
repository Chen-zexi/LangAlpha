import requests
from polygon import RESTClient # Assuming polygon-api-client is installed
from datetime import datetime
from dateutil.relativedelta import relativedelta
import traceback

from .config import POLYGON_API_KEY, ALPHA_VANTAGE_API_KEY
from .utils import safe_float

def get_related_tickers(ticker, polygon_key):
    if not polygon_key:
        print("Polygon API key not available for get_related_tickers.")
        return []
    client = RESTClient(polygon_key)
    try:
        related = client.get_related_companies(ticker.upper())
        return [r.ticker for r in related]
    except Exception as e:
        print(f"Error fetching related companies for {ticker}: {e}")
        return []

def get_alpha_vantage_data(function_name, symbol, api_key):
    """Fetches data from Alpha Vantage API."""
    if not api_key:
        print(f"Alpha Vantage API key missing for {function_name}, {symbol}.")
        return {}
    url = f"https://www.alphavantage.co/query?function={function_name}&symbol={symbol}&apikey={api_key}"
    try:
        response = requests.get(url, timeout=30) 
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Alpha Vantage API request error ({function_name}, {symbol}): {e}")
        return {}
    except ValueError as e: 
        print(f"Alpha Vantage JSON decoding error ({function_name}, {symbol}): {e}")
        return {}

def get_latest_10k_financials(symbol, api_key):
    """
    Fetches and processes the latest 10-K (annual) financial data for a symbol
    from Alpha Vantage.
    """
    print(f"Fetching financial data for {symbol} from Alpha Vantage...")
    overview_data = get_alpha_vantage_data("OVERVIEW", symbol, api_key)
    income_data = get_alpha_vantage_data("INCOME_STATEMENT", symbol, api_key)
    balance_data = get_alpha_vantage_data("BALANCE_SHEET", symbol, api_key)
    quote_data_daily = get_alpha_vantage_data("TIME_SERIES_DAILY", symbol, api_key)

    financials = {}
    try:
        financials["B4"] = overview_data.get("Name", "N/A")
        if financials["B4"] == "N/A":
            print(f"Warning: Could not get company name for {symbol} from OVERVIEW.")
        
        if not overview_data or not income_data or not balance_data:
            error_msg = "One or more Alpha Vantage data sources returned empty."
            api_note = overview_data.get("Note") or income_data.get("Note") or balance_data.get("Note")
            if api_note: error_msg += f" API Note: {api_note}"
            return {"B4": financials.get("B4","N/A"), "error": error_msg}

        inc_reports = income_data.get("annualReports", [])
        bal_reports = balance_data.get("annualReports", [])
        price_series = quote_data_daily.get("Time Series (Daily)", {})

        if not inc_reports or len(inc_reports) < 2:
            return {"B4": financials.get("B4","N/A"), "error": f"Insufficient annual income reports (found {len(inc_reports)})."}
        if not bal_reports or len(bal_reports) < 2:
            return {"B4": financials.get("B4","N/A"), "error": f"Insufficient annual balance sheet reports (found {len(bal_reports)})."}
        
        inc_reports.sort(key=lambda x: x.get("fiscalDateEnding", "0000-00-00"), reverse=True)
        bal_reports.sort(key=lambda x: x.get("fiscalDateEnding", "0000-00-00"), reverse=True)

        inc_curr, inc_prev = inc_reports[0], inc_reports[1]
        bal_curr, bal_prev = bal_reports[0], bal_reports[1]

        financials["B11"] = safe_float(inc_curr.get("totalRevenue"))
        financials["C11"] = safe_float(inc_prev.get("totalRevenue"))
        financials["B12"] = safe_float(inc_curr.get("ebit", inc_curr.get("operatingIncome")))
        financials["C12"] = safe_float(inc_prev.get("ebit", inc_prev.get("operatingIncome")))
        financials["B13"] = safe_float(inc_curr.get("interestExpense"))
        financials["C13"] = safe_float(inc_prev.get("interestExpense"))
        financials["B14"] = safe_float(bal_curr.get("totalShareholderEquity"))
        financials["C14"] = safe_float(bal_prev.get("totalShareholderEquity"))
        financials["B15"] = safe_float(bal_curr.get("shortTermDebt", 0)) + safe_float(bal_curr.get("longTermDebtNoncurrent", bal_curr.get("longTermDebt",0)))
        financials["C15"] = safe_float(bal_prev.get("shortTermDebt", 0)) + safe_float(bal_prev.get("longTermDebtNoncurrent", bal_prev.get("longTermDebt",0)))
        financials["B18"] = safe_float(bal_curr.get("cashAndCashEquivalentsAtCarryingValue"))
        financials["C18"] = safe_float(bal_prev.get("cashAndCashEquivalentsAtCarryingValue"))
        financials["B19"] = safe_float(bal_curr.get("otherCurrentAssets"))
        financials["C19"] = safe_float(bal_prev.get("otherCurrentAssets"))
        financials["B20"] = safe_float(bal_curr.get("minorityInterest", bal_curr.get("noncontrollingInterest", 0))) 
        financials["C20"] = safe_float(bal_prev.get("minorityInterest", bal_prev.get("noncontrollingInterest", 0)))
        financials["B21"] = int(safe_float(overview_data.get("SharesOutstanding", bal_curr.get("commonStockSharesOutstanding", 0))))

        if price_series:
            latest_day = sorted(price_series.keys())[-1]
            financials["B22"] = safe_float(price_series[latest_day].get("4. close"))
        else:
            quote_data_global = get_alpha_vantage_data("GLOBAL_QUOTE", symbol, api_key)
            financials["B22"] = safe_float(quote_data_global.get("Global Quote", {}).get("05. price")) if quote_data_global else 0.0
            if financials["B22"] == 0.0: print(f"Warning: Could not get current stock price for {symbol}.")

        date_curr_str = inc_curr.get("fiscalDateEnding"); date_prev_str = inc_prev.get("fiscalDateEnding")
        if date_curr_str and date_prev_str:
            financials["D11"] = relativedelta(datetime.strptime(date_curr_str, "%Y-%m-%d"), datetime.strptime(date_prev_str, "%Y-%m-%d")).years
        else: financials["D11"] = 1 

        financials["B16"] = "Yes" if safe_float(inc_curr.get("researchAndDevelopment")) > 0 else "No"
        financials["B17"] = "No" # Placeholder for Operating Lease

        income_tax_expense = safe_float(inc_curr.get("incomeTaxExpense"))
        pre_tax_income_direct = safe_float(inc_curr.get("incomeBeforeTax"))
        pre_tax_income = pre_tax_income_direct if pre_tax_income_direct != 0 else (financials.get("B12",0) - financials.get("B13",0))
        financials["B23"] = (income_tax_expense / pre_tax_income) if pre_tax_income != 0 else 0.0
        financials["B24"] = 0.21 # Marginal Tax Rate Placeholder
        
        rf_rate_str = overview_data.get("10YearTreasuryRate", "0.04")
        financials["B34"] = safe_float(rf_rate_str, 0.04) # For cell B34 (Risk-Free Rate)
        if financials["B34"] == 0.04 and rf_rate_str not in ["0.04", "None", None]:
             print(f"Warning: Could not parse 10-Year Treasury Rate '{rf_rate_str}', using default {financials['B34']}.")
        
        print(f"Successfully fetched and processed base financials for {symbol}.")
        return financials

    except KeyError as e:
        print(f"KeyError in get_latest_10k_financials for {symbol}: {e}.")
        return {"B4": financials.get("B4", "N/A"), "error": f"Missing key {e}"}
    except IndexError as e:
        print(f"IndexError in get_latest_10k_financials for {symbol}: {e}.")
        return {"B4": financials.get("B4", "N/A"), "error": f"Insufficient reports {e}"}
    except Exception as e:
        print(f"Unexpected error in get_latest_10k_financials for {symbol}: {e}")
        traceback.print_exc()
        return {"B4": financials.get("B4", "N/A"), "error": f"Unexpected error: {str(e)}"} 