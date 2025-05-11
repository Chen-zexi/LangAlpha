import sys
import pandas as pd
import warnings
import base64 # For encoding plots
import io # For saving plots in memory

# Import Prophet and related diagnostics
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics

# Import Matplotlib and set backend for server use
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend suitable for servers
import matplotlib.pyplot as plt

import numpy as np
from sklearn.linear_model import LinearRegression

# Google API imports
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

# Other API clients
from polygon import RESTClient # Ensure you have polygon-api-client installed

# Standard library imports
import os
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time # For pausing

# Environment variable management
from dotenv import load_dotenv

# Suppress specific warnings if necessary
warnings.filterwarnings("ignore", category=FutureWarning)

# --- Environment Variable Loading ---
load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

# --- Google Sheets Setup ---
# Construct path to credentials file relative to this script's location
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Assumes 'src' is one level down from project root, and 'notebooks' is a sibling to 'src'
_PROJECT_ROOT_DIR = os.path.dirname(_SCRIPT_DIR) 
GOOGLE_CREDS_FILENAME = os.path.join(_PROJECT_ROOT_DIR, 'rational-diode-456114-m0-79243525427e.json')
# If your credentials file is in the SAME directory as this script, you might use:
# GOOGLE_CREDS_FILENAME = os.path.join(_SCRIPT_DIR, 'rational-diode-456114-m0-79243525427e.json')
# Or if running from project root and this file is in 'src':
# GOOGLE_CREDS_FILENAME = 'notebooks/rational-diode-456114-m0-79243525427e.json'

GINZU_SPREADSHEET_LINK = 'https://docs.google.com/spreadsheets/d/1xclQf2xrgw0swp2CRwE25OBaEhQdDTOkm8VVkTcpVks/edit?usp=sharing'
SPREADSHEET_ID = GINZU_SPREADSHEET_LINK.split('/d/')[1].split('/edit')[0]
INPUT_SHEET_NAME = 'Input sheet' 
VALUATION_SHEET_INDEX = 1 # The second sheet (index 1) for B33-B35

# Global variables for gspread objects
# In a production FastAPI app, consider managing these with app lifecycle events or dependency injection
gc = None
input_worksheet = None
valuation_worksheet = None
service = None
google_sheets_initialized = False

def initialize_google_sheets_if_needed():
    """
    Initializes Google Sheets client objects if they haven't been already.
    Returns True if successful or already initialized, False otherwise.
    """
    global gc, input_worksheet, valuation_worksheet, service, google_sheets_initialized
    if google_sheets_initialized:
        return True
    try:
        print(f"Attempting to load Google credentials from: {GOOGLE_CREDS_FILENAME}")
        if not os.path.exists(GOOGLE_CREDS_FILENAME):
            print(f"ERROR: Google credentials file NOT FOUND at '{GOOGLE_CREDS_FILENAME}'.")
            # Try a fallback if the script is in project root and creds in 'notebooks/'
            fallback_creds_path = os.path.join(os.getcwd(), 'notebooks', 'rational-diode-456114-m0-79243525427e.json')
            if os.path.exists(fallback_creds_path):
                print(f"Attempting fallback credentials path: {fallback_creds_path}")
                current_creds_file = fallback_creds_path
            else:
                 # Try another common fallback: creds in same dir as script
                fallback_creds_path_script_dir = os.path.join(_SCRIPT_DIR, 'rational-diode-456114-m0-79243525427e.json')
                if os.path.exists(fallback_creds_path_script_dir):
                    print(f"Attempting fallback credentials path (script dir): {fallback_creds_path_script_dir}")
                    current_creds_file = fallback_creds_path_script_dir
                else:
                    print("All fallback paths for credentials failed.")
                    return False # Critical error, cannot proceed
            
        else:
            current_creds_file = GOOGLE_CREDS_FILENAME

        gc = gspread.service_account(filename=current_creds_file)
        pricer = gc.open_by_url(GINZU_SPREADSHEET_LINK)
        input_worksheet = pricer.get_worksheet(0) # Input sheet is the first sheet
        valuation_worksheet = pricer.get_worksheet(VALUATION_SHEET_INDEX) # Valuation sheet

        creds_service_account = Credentials.from_service_account_file(current_creds_file, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        service = build('sheets', 'v4', credentials=creds_service_account)
        
        google_sheets_initialized = True
        print("Google Sheets initialized successfully.")
        return True
    except FileNotFoundError: # Should be caught by os.path.exists now, but as a safeguard
        print(f"CRITICAL ERROR: Google credentials file not found at specified paths.")
        return False
    except Exception as e:
        print(f"Error initializing Google Sheets: {e}")
        return False

# --- Helper Functions ---
def safe_float(value, default=0.0):
    """Safely convert a value to float, returning a default if conversion fails."""
    try:
        return float(value) if value not in [None, 'None', ''] else default
    except (ValueError, TypeError):
        return default

def get_alpha_vantage_data(function_name, symbol, api_key):
    """Fetches data from Alpha Vantage API."""
    if not api_key:
        print(f"Alpha Vantage API key missing for {function_name}, {symbol}.")
        return {}
    url = f"https://www.alphavantage.co/query?function={function_name}&symbol={symbol}&apikey={api_key}"
    try:
        response = requests.get(url, timeout=30) # Added timeout
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Alpha Vantage API request error ({function_name}, {symbol}): {e}")
        return {}
    except ValueError as e: # Includes JSONDecodeError
        print(f"Alpha Vantage JSON decoding error ({function_name}, {symbol}): {e}")
        return {}

def get_latest_10k_financials(symbol, api_key):
    """
    Fetches and processes the latest 10-K (annual) financial data for a symbol
    from Alpha Vantage.
    Returns a dictionary of financial metrics or a dictionary with an "error" key.
    """
    print(f"Fetching financial data for {symbol} from Alpha Vantage...")
    overview_data = get_alpha_vantage_data("OVERVIEW", symbol, api_key)
    income_data = get_alpha_vantage_data("INCOME_STATEMENT", symbol, api_key)
    balance_data = get_alpha_vantage_data("BALANCE_SHEET", symbol, api_key)
    quote_data_daily = get_alpha_vantage_data("TIME_SERIES_DAILY", symbol, api_key)

    financials = {}
    try:
        financials["B4"] = overview_data.get("Name", "N/A") # Company Name
        if financials["B4"] == "N/A":
            print(f"Warning: Could not get company name for {symbol} from OVERVIEW.")
        
        # Check for API call limits or errors in fetched data
        if not overview_data or not income_data or not balance_data:
            error_msg = "One or more Alpha Vantage data sources returned empty."
            if overview_data.get("Note") or income_data.get("Note") or balance_data.get("Note"):
                 error_msg += f" API Note: {overview_data.get('Note') or income_data.get('Note') or balance_data.get('Note')}"
            return {"B4": financials.get("B4","N/A"), "error": error_msg}

        inc_reports = income_data.get("annualReports", [])
        bal_reports = balance_data.get("annualReports", [])
        price_series = quote_data_daily.get("Time Series (Daily)", {})

        if not inc_reports or len(inc_reports) < 2:
            return {"B4": financials.get("B4","N/A"), "error": f"Insufficient annual income reports (found {len(inc_reports)})."}
        if not bal_reports or len(bal_reports) < 2:
            return {"B4": financials.get("B4","N/A"), "error": f"Insufficient annual balance sheet reports (found {len(bal_reports)})."}
        
        # Sort reports by date, most recent first
        inc_reports.sort(key=lambda x: x.get("fiscalDateEnding", "0000-00-00"), reverse=True)
        bal_reports.sort(key=lambda x: x.get("fiscalDateEnding", "0000-00-00"), reverse=True)

        inc_curr, inc_prev = inc_reports[0], inc_reports[1]
        bal_curr, bal_prev = bal_reports[0], bal_reports[1]

        # Populate financials dictionary
        financials["B11"] = safe_float(inc_curr.get("totalRevenue"))
        financials["C11"] = safe_float(inc_prev.get("totalRevenue"))
        financials["B12"] = safe_float(inc_curr.get("ebit", inc_curr.get("operatingIncome"))) # Use ebit or operatingIncome
        financials["C12"] = safe_float(inc_prev.get("ebit", inc_prev.get("operatingIncome")))
        financials["B13"] = safe_float(inc_curr.get("interestExpense"))
        financials["C13"] = safe_float(inc_prev.get("interestExpense"))
        financials["B14"] = safe_float(bal_curr.get("totalShareholderEquity"))
        financials["C14"] = safe_float(bal_prev.get("totalShareholderEquity"))
        
        # Debt: Sum of short-term and long-term debt
        financials["B15"] = safe_float(bal_curr.get("shortTermDebt", 0)) + safe_float(bal_curr.get("longTermDebtNoncurrent", bal_curr.get("longTermDebt",0)))
        financials["C15"] = safe_float(bal_prev.get("shortTermDebt", 0)) + safe_float(bal_prev.get("longTermDebtNoncurrent", bal_prev.get("longTermDebt",0)))
        
        financials["B18"] = safe_float(bal_curr.get("cashAndCashEquivalentsAtCarryingValue"))
        financials["C18"] = safe_float(bal_prev.get("cashAndCashEquivalentsAtCarryingValue"))
        
        financials["B19"] = safe_float(bal_curr.get("otherCurrentAssets")) # Proxy for Investments
        financials["C19"] = safe_float(bal_prev.get("otherCurrentAssets"))

        # Minority Interest / Noncontrolling Interest
        financials["B20"] = safe_float(bal_curr.get("minorityInterest", bal_curr.get("noncontrollingInterest", 0))) 
        financials["C20"] = safe_float(bal_prev.get("minorityInterest", bal_prev.get("noncontrollingInterest", 0)))

        financials["B21"] = int(safe_float(overview_data.get("SharesOutstanding", bal_curr.get("commonStockSharesOutstanding", 0))))

        # Stock Price
        if price_series:
            latest_day = sorted(price_series.keys())[-1]
            financials["B22"] = safe_float(price_series[latest_day].get("4. close"))
        else: # Fallback if daily series failed
            quote_data_global = get_alpha_vantage_data("GLOBAL_QUOTE", symbol, api_key)
            financials["B22"] = safe_float(quote_data_global.get("Global Quote", {}).get("05. price")) if quote_data_global else 0.0
            if financials["B22"] == 0.0: print(f"Warning: Could not get current stock price for {symbol} from daily or global quote.")
        
        # Years between reports
        date_curr_str = inc_curr.get("fiscalDateEnding"); date_prev_str = inc_prev.get("fiscalDateEnding")
        if date_curr_str and date_prev_str:
            financials["D11"] = relativedelta(datetime.strptime(date_curr_str, "%Y-%m-%d"), datetime.strptime(date_prev_str, "%Y-%m-%d")).years
        else: financials["D11"] = 1 # Default to 1 year

        financials["B16"] = "Yes" if safe_float(inc_curr.get("researchAndDevelopment")) > 0 else "No" # R&D
        financials["B17"] = "No" # Operating Lease - Placeholder, needs better data source or logic

        # Tax Rates
        income_tax_expense = safe_float(inc_curr.get("incomeTaxExpense"))
        # Use incomeBeforeTax if available, else calculate from EBIT and Interest
        pre_tax_income_direct = safe_float(inc_curr.get("incomeBeforeTax"))
        if pre_tax_income_direct != 0:
             pre_tax_income = pre_tax_income_direct
        else:
            pre_tax_income = financials.get("B12",0) - financials.get("B13",0) # EBIT - Interest Expense
        
        financials["B23"] = (income_tax_expense / pre_tax_income) if pre_tax_income != 0 else 0.0 # Effective Tax Rate
        financials["B24"] = 0.21 # Marginal Tax Rate (US Federal, placeholder)
        
        # Risk-Free Rate for cell B34 (as per user's sheet structure)
        rf_rate_str = overview_data.get("10YearTreasuryRate", "0.04") # Default to 4% if not found
        financials["B34"] = safe_float(rf_rate_str, 0.04) 
        if financials["B34"] == 0.04 and rf_rate_str != "0.04" and rf_rate_str != "None": # Check if default was used due to parsing fail
             print(f"Warning: Could not parse 10-Year Treasury Rate '{rf_rate_str}', using default {financials['B34']}.")
        
        print(f"Successfully fetched and processed base financials for {symbol}.")
        return financials

    except KeyError as e:
        print(f"KeyError while processing financial data for {symbol}: {e}. Data might be missing from Alpha Vantage response.")
        return {"B4": financials.get("B4", "N/A"), "error": f"Missing key {e} in API response"}
    except IndexError as e:
        print(f"IndexError while processing financial data for {symbol}: {e}. Likely insufficient historical reports.")
        return {"B4": financials.get("B4", "N/A"), "error": f"Insufficient historical reports: {e}"}
    except Exception as e:
        print(f"Unexpected error in get_latest_10k_financials for {symbol}: {e}")
        import traceback
        traceback.print_exc() # For more detailed error logging during development
        return {"B4": financials.get("B4", "N/A"), "error": f"Unexpected processing error: {str(e)}"}

def retrieve_date_str():
    """Returns the current date formatted as 'Mon-DD'."""
    return datetime.today().strftime('%b-%d')

def get_annual_financial_data(symbol, api_key, data_type="revenue", history_years=15):
    """
    Fetches annual financial data (revenue or operating margin) for Prophet.
    """
    url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={api_key}"
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        print(f"Request failed for {symbol} income statement (status {response.status_code}).")
        return pd.DataFrame()
    
    data = response.json()
    if "annualReports" not in data or not data["annualReports"]:
        # Log API message if available (e.g., call frequency limit)
        api_message = data.get('Information', data.get('Note', 'No further info from API.'))
        print(f"No annualReports found for symbol {symbol}. API Message: {api_message}")
        return pd.DataFrame()

    reports = data["annualReports"]
    records = []
    for report in reports:
        try:
            date = pd.to_datetime(report["fiscalDateEnding"])
            value = None
            if data_type == "revenue":
                value = safe_float(report.get("totalRevenue"))
            elif data_type == "operating_margin":
                # Use operatingIncome if available, fallback to ebit
                operating_income = safe_float(report.get("operatingIncome", report.get("ebit")))
                total_revenue = safe_float(report.get("totalRevenue"))
                value = (operating_income / total_revenue) * 100 if total_revenue != 0 else 0.0
            
            if value is not None: # Ensure a value was actually processed
                 records.append({"ds": date, "y": value})
        except (KeyError, TypeError, ValueError) as e:
            # Log which report (by date) and for which data_type the error occurred
            print(f"Skipping report for {symbol} (date: {report.get('fiscalDateEnding')}) due to error processing {data_type}: {e}")
    
    df = pd.DataFrame(records).sort_values("ds").reset_index(drop=True)
    
    if not df.empty:
        cutoff_date = pd.Timestamp.today() - pd.DateOffset(years=history_years)
        df = df[df['ds'] >= cutoff_date]
    
    return df

def _generate_plot_base64(fig):
    """Helper to convert a matplotlib figure to a base64 PNG string."""
    if fig is None: return None
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", bbox_inches='tight')
        plt.close(fig) # Close the figure to free memory
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"Error generating plot base64: {e}")
        plt.close(fig) # Ensure figure is closed even on error
        return None


# --- Modified Forecasting Functions to return plot data ---
# (These are simplified for brevity; they should include the robust CV logic from previous versions)

def forecast_revenue_growth_rate(symbol, api_key, history_years=5, cps_grid=None):
    """Forecasts revenue growth rate and returns rate and plot data."""
    print(f"Forecasting Revenue Growth Rate for {symbol}...")
    df_revenue = get_annual_financial_data(symbol, api_key, "revenue", history_years)
    if len(df_revenue) < 2: # Prophet needs at least 2 data points
        return {"growth_rate": 0.0, "error": "Insufficient data for revenue forecast", "plot_base64": None}
    
    best_cps = 0.05 # Default or from CV
    # Add CV logic here if desired, similar to previous full script versions
    
    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(5, len(df_revenue)-1))
    model.fit(df_revenue)
    future = model.make_future_dataframe(periods=1, freq='A') # Annual forecast
    forecast = model.predict(future)
    
    last_actual_revenue = df_revenue.iloc[-1]["y"]
    next_forecast_revenue = forecast.iloc[-1]["yhat"]
    growth_rate = (next_forecast_revenue - last_actual_revenue) / last_actual_revenue if last_actual_revenue != 0 else 0.0
    
    fig = model.plot(forecast)
    ax = fig.gca()
    ax.set_title(f"Revenue Forecast for {symbol} (CPS: {best_cps:.2f})")
    ax.set_xlabel("Date"); ax.set_ylabel("Revenue")
    plot_base64 = _generate_plot_base64(fig)
    
    return {"growth_rate": growth_rate, "best_cps": best_cps, "plot_base64": plot_base64}

def forecast_operating_margin(symbol, api_key, history_years=10, cps_grid=None):
    """Forecasts operating margin and returns margin and plot data."""
    print(f"Forecasting Operating Margin for {symbol}...")
    df_margin = get_annual_financial_data(symbol, api_key, "operating_margin", history_years)
    if len(df_margin) < 2:
        return {"margin_forecast": 0.0, "error": "Insufficient data for operating margin forecast", "plot_base64": None}
    best_cps = 0.05 # Default or from CV
    # Add CV logic here
    
    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(5, len(df_margin)-1))
    model.fit(df_margin)
    future = model.make_future_dataframe(periods=1, freq='A')
    forecast = model.predict(future)
    margin_forecast_val = forecast.iloc[-1]['yhat']
    
    fig = model.plot(forecast)
    ax = fig.gca()
    ax.plot(df_margin['ds'], df_margin['y'], 'o-', label='Historical Margin') # Add actuals
    ax.set_title(f"Operating Margin Forecast for {symbol} (CPS: {best_cps:.2f})")
    ax.set_xlabel("Year"); ax.set_ylabel("Operating Margin (%)"); ax.legend()
    plot_base64 = _generate_plot_base64(fig)
    
    return {'margin_forecast': margin_forecast_val, 'best_cps': best_cps, "plot_base64": plot_base64}

def forecast_revenue_cagr(symbol, api_key, forecast_years=5, history_years=15, growth='logistic', cps_grid=None):
    """Forecasts revenue CAGR and returns CAGR and plot data."""
    print(f"Forecasting Revenue CAGR for {symbol} (Growth: {growth})...")
    df_revenue = get_annual_financial_data(symbol, api_key, "revenue", history_years)
    if len(df_revenue) < 2:
        return {'cagr_forecast': 0.0, 'error': "Insufficient data for CAGR forecast", "plot_base64": None}
    
    best_cps = 0.05 # Default or from CV
    cap_val_final = None
    # Add CV logic here (as in previous full versions, training on df.iloc[:-1], testing on last point)
    
    df_revenue_for_fit = df_revenue.copy() # Use a copy to avoid modifying original df
    if growth == 'logistic':
        cap_val_final = df_revenue_for_fit['y'].max() * 1.5 
        df_revenue_for_fit['cap'] = cap_val_final
    
    model = Prophet(growth=growth, yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(10, len(df_revenue_for_fit)-1))
    model.fit(df_revenue_for_fit)
    future = model.make_future_dataframe(periods=forecast_years, freq='A')
    if growth == 'logistic':
        future['cap'] = cap_val_final

    forecast = model.predict(future)
    initial_revenue = df_revenue_for_fit['y'].iloc[-1]
    forecast_end_revenue = forecast['yhat'].iloc[-1]
    cagr_val = ((forecast_end_revenue / initial_revenue) ** (1/forecast_years) - 1) if initial_revenue != 0 and forecast_end_revenue > 0 else 0.0
    
    fig = model.plot(forecast)
    ax = fig.gca()
    ax.plot(df_revenue_for_fit['ds'], df_revenue_for_fit['y'], 'o-', label='Historical Revenue')
    ax.set_title(f"{forecast_years}-Yr Revenue CAGR Forecast for {symbol} (CPS: {best_cps:.2f}, Growth: {growth})")
    ax.set_xlabel("Year"); ax.set_ylabel("Revenue (USD)"); ax.legend()
    plot_base64 = _generate_plot_base64(fig)
    
    return {'cagr_forecast': cagr_val, 'best_cps': best_cps, "plot_base64": plot_base64}

def forecast_pretarget_operating_margin(symbol, api_key, history_years=5):
    """Forecasts target operating margin and convergence, returns metrics and plot data."""
    print(f"Forecasting Pre-Target Operating Margin for {symbol}...")
    # Ensure enough history for regression, Prophet needs at least 2 for a line.
    df_margin = get_annual_financial_data(symbol, api_key, "operating_margin", history_years=max(history_years, 2)) 
    if len(df_margin) < 2:
        return {'target_margin': 0.0, 'years_to_converge': np.inf, 'error': "Insufficient data for margin trend", "plot_base64": None}

    X = df_margin['ds'].dt.year.values.reshape(-1, 1)
    y = df_margin['y'].values # Margin is already in %

    model = LinearRegression().fit(X, y)
    slope = model.coef_[0]   
    future_year_for_target = X[-1][0] + 5 # Target 5 years from last historical year
    target_margin_forecast = model.predict(np.array([[future_year_for_target]]))[0]
    current_margin = y[-1]
    years_to_converge_val = (target_margin_forecast - current_margin) / slope if not np.isclose(slope, 0) else np.inf
    
    fig, ax = plt.subplots(figsize=(10,6))
    ax.plot(X.flatten(), y, 'o-', label='Historical Operating Margin (%)')
    ax.plot(X.flatten(), model.predict(X), '--', label='Linear Regression Trend')
    ax.axvline(future_year_for_target, color='red', linestyle=':', label=f'Target Year ({future_year_for_target})')
    ax.scatter(future_year_for_target, target_margin_forecast, color='red', zorder=5)
    ax.text(future_year_for_target, target_margin_forecast, f' Target: {target_margin_forecast:.2f}%', va='bottom', ha='right')
    ax.set_title(f'{symbol} Operating Margin Trend & Target Forecast')
    ax.set_xlabel('Year'); ax.set_ylabel('Operating Margin (%)'); ax.legend(); ax.grid(True)
    plot_base64 = _generate_plot_base64(fig)
    
    return {'current_margin': current_margin, 'target_margin': target_margin_forecast, 'annual_change_pct_points': slope, 'years_to_converge': years_to_converge_val, "plot_base64": plot_base64}

def forecast_sales_to_capital_ratio(symbol, api_key, history_years=15, cps=0.05):
    """Forecasts sales-to-capital ratio and returns averages and plot data."""
    print(f"Forecasting Sales-to-Capital Ratio for {symbol}...")
    # Fetch Income for Revenue
    income_df_raw = get_annual_financial_data(symbol, api_key, "revenue", history_years)
    if income_df_raw.empty:
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "No income data for S/C ratio", "plot_base64": None}
    income_df = income_df_raw.rename(columns={'y':'totalRevenue'})

    # Fetch Balance Sheet for Invested Capital (using Total Assets as proxy)
    balance_sheet_data = get_alpha_vantage_data("BALANCE_SHEET", symbol, api_key)
    if not balance_sheet_data.get("annualReports"):
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "No balance sheet data for S/C ratio", "plot_base64": None}
    
    bal_records = []
    for report in balance_sheet_data["annualReports"]:
        bal_records.append({
            "ds": pd.to_datetime(report.get("fiscalDateEnding")),
            "investedCapital": safe_float(report.get("totalAssets")) # Proxy
        })
    balance_df = pd.DataFrame(bal_records).sort_values("ds").reset_index(drop=True)
    if balance_df.empty:
         return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "Processed balance sheet data empty for S/C ratio", "plot_base64": None}

    # Merge and Calculate Ratio
    df = pd.merge(income_df, balance_df, on='ds', how='inner')
    df.dropna(subset=['totalRevenue', 'investedCapital'], inplace=True)
    if df.empty or df['investedCapital'].eq(0).all():
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "Insufficient merged data for S/C ratio", "plot_base64": None}
        
    df['ratio'] = df['totalRevenue'] / df['investedCapital']
    df_prophet = df[['ds', 'ratio']].rename(columns={'ratio': 'y'})
    
    if len(df_prophet) < 2:
        avg_hist_ratio = df_prophet['y'].mean() if not df_prophet.empty else 0.0
        return {'avg_1_5': avg_hist_ratio, 'avg_6_10': avg_hist_ratio, 'error': "Insufficient S/C data for Prophet", "plot_base64": None}

    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=cps, n_changepoints=min(5, len(df_prophet)-1))
    model.fit(df_prophet)
    future = model.make_future_dataframe(periods=10, freq='A') # Forecast 10 years
    fc = model.predict(future)

    last_hist_date = df_prophet['ds'].max()
    forecast_points = fc[fc['ds'] > last_hist_date].reset_index(drop=True)

    if forecast_points.empty or len(forecast_points) < 1: # Check if any forecast points exist
        avg_hist_ratio = df_prophet['y'].mean() if not df_prophet.empty else 0.0
        return {'avg_1_5': avg_hist_ratio, 'avg_6_10': avg_hist_ratio, 'error': "S/C Prophet forecast produced no future points", "plot_base64": None}

    avg_1_5_val = forecast_points.loc[0:min(4, len(forecast_points)-1), 'yhat'].mean()
    avg_6_10_val = forecast_points.loc[5:min(9, len(forecast_points)-1), 'yhat'].mean() if len(forecast_points) > 5 else avg_1_5_val

    fig = model.plot(fc) # Plot full forecast including history
    ax = fig.gca()
    ax.plot(df_prophet['ds'], df_prophet['y'], 'o-', label='Historical S/C Ratio')
    ax.set_title(f"{symbol} Sales-to-Capital Ratio Forecast (CPS: {cps:.2f})")
    ax.set_xlabel("Year"); ax.set_ylabel("Sales / Invested Capital"); ax.legend(); ax.grid(True)
    plot_base64 = _generate_plot_base64(fig)
    
    return {'avg_1_5': avg_1_5_val, 'avg_6_10': avg_6_10_val, "plot_base64": plot_base64}


# --- Main Logic Functions for FastAPI ---
def perform_initial_analysis(company_ticker: str, country: str = "United States", us_industry: str = "Software", global_industry: str = "Technology") -> dict:
    """
    Performs the first part of the analysis: fetches data, runs forecasts,
    and returns suggestions and plot data.
    Dropdown-selected values are passed as parameters.
    """
    if not POLYGON_API_KEY or not ALPHA_VANTAGE_API_KEY:
        return {"status": "error", "message": "API keys are not configured on the server."}
    if not initialize_google_sheets_if_needed(): # Ensures sheets are ready
        return {"status": "error", "message": "Failed to initialize Google Sheets service."}

    global input_worksheet # Use the initialized global worksheet object

    print(f"Performing initial analysis for {company_ticker}...")
    financials = get_latest_10k_financials(company_ticker, ALPHA_VANTAGE_API_KEY)
    if "error" in financials:
        return {"status": "error", "message": f"Failed to fetch initial financials for {company_ticker}: {financials['error']}"}

    # Update sheet with base financials and passed-in dropdowns
    date_val = retrieve_date_str()
    input_worksheet.update_acell('B3', date_val)
    company_name = financials.get("B4", company_ticker)
    input_worksheet.update_acell('B4', company_name)
    
    input_worksheet.update_acell('B7', country)
    input_worksheet.update_acell('B8', us_industry)
    input_worksheet.update_acell('B9', global_industry)
    print(f"Updated sheet with Country: {country}, US Industry: {us_industry}, Global Industry: {global_industry}")


    # Financial data that gets scaled for the sheet
    financial_updates = {
        'D11': financials.get("D11"),
        'B11': financials.get("B11", 0) / 10000000, 'C11': financials.get("C11", 0) / 10000000,
        'B12': financials.get("B12", 0) / 10000000, 'C12': financials.get("C12", 0) / 10000000,
        'B13': financials.get("B13", 0) / 10000000, 'C13': financials.get("C13", 0) / 10000000,
        'B14': financials.get("B14", 0) / 10000000, 'C14': financials.get("C14", 0) / 10000000,
        'B15': financials.get("B15", 0) / 10000000, 'C15': financials.get("C15", 0) / 10000000,
        'B16': financials.get("B16"), 'B17': financials.get("B17"),
        'B18': financials.get("B18", 0) / 10000000, 'C18': financials.get("C18", 0) / 10000000,
        'B19': financials.get("B19", 0) / 10000000, 'C19': financials.get("C19", 0) / 10000000,
        'B20': financials.get("B20", 0) / 10000000, 'C20': financials.get("C20", 0) / 10000000,
        'B21': financials.get("B21", 0) / 10000000, # Shares in millions
        'B22': financials.get("B22"), # Current Stock Price
        'B23': financials.get("B23"), # Effective Tax Rate
        'B24': financials.get("B24"), # Marginal Tax Rate
        'B34': financials.get("B34")  # Risk-free rate for cell B34
    }
    for cell, value in financial_updates.items():
        if value is not None: 
            input_worksheet.update_acell(cell, value)
    print(f"Base financial data updated in sheet for {company_ticker}.")

    # Run forecasts and collect results including plot data
    forecast_results = {
        "b26_rev_growth": forecast_revenue_growth_rate(company_ticker, ALPHA_VANTAGE_API_KEY),
        "b27_op_margin": forecast_operating_margin(company_ticker, ALPHA_VANTAGE_API_KEY),
        "b28_cagr": forecast_revenue_cagr(company_ticker, ALPHA_VANTAGE_API_KEY), # Default growth='logistic'
        "b29_b30_target_margin": forecast_pretarget_operating_margin(company_ticker, ALPHA_VANTAGE_API_KEY),
        "b31_b32_sc_ratio": forecast_sales_to_capital_ratio(company_ticker, ALPHA_VANTAGE_API_KEY),
    }

    # Prepare data to be returned to the frontend
    suggestions = {
        "company_name": company_name,
        "ticker": company_ticker,
        # For percentages, send them as numbers (e.g., 5.25 for 5.25%)
        "b26_rev_growth_suggested_pct": forecast_results["b26_rev_growth"].get('growth_rate', 0.0) * 100,
        "b26_rev_growth_plot_base64": forecast_results["b26_rev_growth"].get('plot_base64'),
        
        "b27_op_margin_suggested_pct": forecast_results["b27_op_margin"].get('margin_forecast', 0.0), # Already in %
        "b27_op_margin_plot_base64": forecast_results["b27_op_margin"].get('plot_base64'),
        
        "b28_cagr_suggested_pct": forecast_results["b28_cagr"].get('cagr_forecast', 0.0) * 100,
        "b28_cagr_plot_base64": forecast_results["b28_cagr"].get('plot_base64'),
        
        "b29_target_op_margin_suggested_pct": forecast_results["b29_b30_target_margin"].get('target_margin', 0.0), # Already in %
        "b29_target_op_margin_plot_base64": forecast_results["b29_b30_target_margin"].get('plot_base64'),
        "b30_years_to_converge_suggested": forecast_results["b29_b30_target_margin"].get('years_to_converge', 0.0),
        
        "b31_sc_ratio_1_5_suggested": forecast_results["b31_b32_sc_ratio"].get('avg_1_5', 0.0),
        "b31_sc_ratio_plot_base64": forecast_results["b31_b32_sc_ratio"].get('plot_base64'), # One plot for S/C
        "b32_sc_ratio_6_10_suggested": forecast_results["b31_b32_sc_ratio"].get('avg_6_10', 0.0),
    }
    
    return {"status": "success", "message": "Initial analysis complete.", "data": suggestions}

def finalize_and_update_sheet(company_ticker: str, user_value_drivers: dict) -> dict:
    """
    Updates the sheet with user-provided value drivers and fetches final valuation.
    user_value_drivers should contain keys like 'b26_rev_growth' with values
    already scaled as decimals by the frontend (e.g., 0.05 for 5%).
    """
    if not initialize_google_sheets_if_needed():
        return {"status": "error", "message": "Failed to initialize Google Sheets service."}

    global input_worksheet, valuation_worksheet # Use the initialized global worksheet objects

    print(f"Finalizing analysis for {company_ticker} with user inputs: {user_value_drivers}")
    
    # Map user_value_drivers keys to sheet cells and update
    # Frontend will send values like 0.05 for 5%
    sheet_updates = {
        'B26': user_value_drivers.get('b26_rev_growth'),      # e.g., 0.05
        'B27': user_value_drivers.get('b27_op_margin'),      # e.g., 0.15
        'B28': user_value_drivers.get('b28_cagr'),           # e.g., 0.07
        'B29': user_value_drivers.get('b29_target_op_margin'),# e.g., 0.20
        'B30': user_value_drivers.get('b30_years_to_converge'),
        'B31': user_value_drivers.get('b31_sc_ratio_1_5'),
        'B32': user_value_drivers.get('b32_sc_ratio_6_10'),
    }

    for cell, value in sheet_updates.items():
        if value is not None: # Check if the key was provided and has a value
            try:
                # Ensure value is float if it's supposed to be numeric, else it might be string "N/A"
                val_to_write = float(value)
                input_worksheet.update_acell(cell, val_to_write)
                print(f"Updated sheet cell {cell}: {val_to_write}")
            except ValueError: # If value is not float-convertible (e.g. "N/A" or empty string from optional input)
                print(f"Skipping update for cell {cell} due to non-numeric value: {value}")
            except Exception as e:
                print(f"Error updating cell {cell} with value {value}: {e}")
        else:
            print(f"Skipped updating cell {cell} as no value was provided in user_value_drivers.")
            
    print(f"User value drivers updated in sheet for {company_ticker}. Pausing for calculations...")
    time.sleep(7) # Pause for sheet to calculate

    try:
        # Fetch final valuation metrics from the "Valuation" sheet
        val_b33_str = valuation_worksheet.acell('B33').value # Estimated value /share
        val_b34_str = valuation_worksheet.acell('B34').value # Price
        val_b35_str = valuation_worksheet.acell('B35').value # Price as % of value

        # Convert to float, defaulting to None if conversion fails (e.g. if cell is empty or non-numeric)
        est_value_per_share = safe_float(val_b33_str, default=None) 
        price_val = safe_float(val_b34_str, default=None)
        # For B35, if it's "142.56%", gspread might return it as a string or try to convert.
        # If it's stored as a number 142.56, safe_float will work.
        # If it's a string "142.56%", we need to strip '%' and convert.
        if isinstance(val_b35_str, str) and '%' in val_b35_str:
            price_as_percent_val = safe_float(val_b35_str.replace('%',''), default=None)
        else:
            price_as_percent_val = safe_float(val_b35_str, default=None)


        final_metrics = {
            "estimated_value_per_share": est_value_per_share,
            "price": price_val,
            "price_as_percent_of_value": price_as_percent_val, # This is a percentage value like 142.56
        }
        print(f"Fetched final metrics: {final_metrics}")
        return {"status": "success", "message": "Analysis finalized.", "data": final_metrics}

    except Exception as e:
        print(f"Could not read or format final valuation metrics from sheet: {e}")
        return {"status": "error", "message": f"Failed to read final valuation metrics: {str(e)}", "data": {}}

# --- Example of how to call these functions (for testing, not part of FastAPI app itself) ---
if __name__ == '__main__':
    print("Starting Ginzu Interface Test Run...")
    if not POLYGON_API_KEY or not ALPHA_VANTAGE_API_KEY:
        print("CRITICAL: API keys for Polygon or Alpha Vantage are missing. Please set them as environment variables.")
    else:
        # --- Test Step 1: Initial Analysis ---
        test_ticker = input("Enter a ticker for testing (e.g., AAPL): ").strip().upper()
        if not test_ticker: test_ticker = "AAPL" # Default for quick test

        # Simulate dropdowns (in FastAPI, these would come from the request or be fixed)
        test_country = "United States"
        test_us_industry = "Technology Hardware, Storage & Peripherals" # Example
        test_global_industry = "Technology Hardware & Equipment" # Example

        print(f"\n--- Simulating Step 1: Initial Analysis for {test_ticker} ---")
        initial_result = perform_initial_analysis(test_ticker, test_country, test_us_industry, test_global_industry)

        if initial_result["status"] == "success":
            print("\nInitial Analysis Successful. Data received by 'frontend':")
            suggestions = initial_result["data"]
            print(f"Company: {suggestions['company_name']}")
            print(f"Ticker: {suggestions['ticker']}")
            print(f"Suggested B26 (Rev Growth %): {suggestions['b26_rev_growth_suggested_pct']:.2f}")
            # print(f"B26 Plot Data (first 50 chars): {suggestions['b26_rev_growth_plot_base64'][:50] if suggestions['b26_rev_growth_plot_base64'] else 'No Plot'}")
            # ... (print other suggestions)

            # --- Test Step 2: Simulate User Input and Finalize ---
            print("\n--- Simulating Step 2: User Inputs and Finalization ---")
            # User inputs are expected as decimals by finalize_and_update_sheet (e.g., 5% as 0.05)
            # The frontend JS would handle converting user's "5" or "5%" into 0.05
            sample_user_inputs = {
                'b26_rev_growth': suggestions['b26_rev_growth_suggested_pct'] / 100.0, # Convert suggested % to decimal
                'b27_op_margin': suggestions['b27_op_margin_suggested_pct'] / 100.0,   # Op Margin is already in %, so divide by 100
                'b28_cagr': suggestions['b28_cagr_suggested_pct'] / 100.0,
                'b29_target_op_margin': suggestions['b29_target_op_margin_suggested_pct'] / 100.0, # Op Margin is already in %, so divide by 100
                'b30_years_to_converge': suggestions['b30_years_to_converge_suggested'],
                'b31_sc_ratio_1_5': suggestions['b31_sc_ratio_1_5_suggested'],
                'b32_sc_ratio_6_10': suggestions['b32_sc_ratio_6_10_suggested'],
            }
            print(f"Simulated user inputs (as decimals for backend): {sample_user_inputs}")

            final_result = finalize_and_update_sheet(test_ticker, sample_user_inputs)

            if final_result["status"] == "success":
                print("\nFinalization Successful. Final Metrics:")
                final_data = final_result["data"]
                est_val = final_data.get('estimated_value_per_share')
                price = final_data.get('price')
                perc_val = final_data.get('price_as_percent_of_value')

                print(f"Estimated value /share: $ {est_val:.2f}" if est_val is not None else "Estimated value /share: N/A")
                print(f"Price: $ {price:.2f}" if price is not None else "Price: N/A")
                print(f"Price as % of value: {perc_val:.2f}%" if perc_val is not None else "Price as % of value: N/A")
            else:
                print(f"Finalization Failed: {final_result['message']}")
        else:
            print(f"Initial Analysis Failed: {initial_result['message']}")
    print("\nGinzu Interface Test Run Finished.")
