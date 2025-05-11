import sys
import pandas as pd
import warnings

from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

from polygon import RESTClient

import os
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Environment Variable Loading ---
load_dotenv()
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

if not POLYGON_API_KEY:
    print("Warning: POLYGON_API_KEY not found in environment variables.")
if not ALPHA_VANTAGE_API_KEY:
    print("Warning: ALPHA_VANTAGE_API_KEY not found in environment variables.")

# --- Google Sheets Setup ---
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT_DIR = os.path.dirname(_SCRIPT_DIR)

GOOGLE_CREDS_FILENAME = os.path.join(_PROJECT_ROOT_DIR, 'gcp_credential.json')

GINZU_SPREADSHEET_LINK = 'https://docs.google.com/spreadsheets/d/1xclQf2xrgw0swp2CRwE25OBaEhQdDTOkm8VVkTcpVks/edit?usp=sharing'
SPREADSHEET_ID = GINZU_SPREADSHEET_LINK.split('/d/')[1].split('/edit')[0]
INPUT_SHEET_NAME = 'Input sheet' 
VALUATION_SHEET_INDEX = 1

gc = None
input_worksheet = None
valuation_worksheet = None
service = None

def initialize_google_sheets():
    global gc, input_worksheet, valuation_worksheet, service
    try:
        print(f"Attempting to load Google credentials from: {GOOGLE_CREDS_FILENAME}")
        gc = gspread.service_account(filename=GOOGLE_CREDS_FILENAME)
        pricer = gc.open_by_url(GINZU_SPREADSHEET_LINK)
        input_worksheet = pricer.get_worksheet(0)
        valuation_worksheet = pricer.get_worksheet(VALUATION_SHEET_INDEX)

        creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILENAME, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        service = build('sheets', 'v4', credentials=creds)
        print("Google Sheets initialized successfully.")
    except FileNotFoundError:
        print(f"ERROR: Google credentials file not found at '{GOOGLE_CREDS_FILENAME}'.")
        print("Please ensure the path is correct and the file exists.")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing Google Sheets: {e}")
        print("Please ensure your Google credentials file is correctly set up, the sheet URL is accessible, and the service account has permissions.")
        sys.exit(1)

# --- Helper Functions ---
def safe_float(value, default=0.0):
    try:
        return float(value) if value not in [None, 'None', ''] else default
    except (ValueError, TypeError):
        return default

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

def get_dropdown_options(spreadsheet_id: str, sheet_name: str, cell: str) -> list:
    if not service:
        print("Google Sheets service not initialized. Cannot get dropdown options.")
        return []
    range_name = f"'{sheet_name}'!{cell}"
    try:
        response = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_name],
            includeGridData=True,
            fields='sheets.data.rowData.values.dataValidation'
        ).execute()

        validation_path = response.get('sheets', [{}])[0].get('data', [{}])[0].get('rowData', [{}])[0].get('values', [{}])[0].get('dataValidation')
        if not validation_path:
            print(f"No data validation found at {sheet_name}!{cell}.")
            return []
            
        condition = validation_path['condition']
        dropdown_values = [v['userEnteredValue'] for v in condition.get('values', [])]

        if not dropdown_values:
             return []

        dropdown_ref = dropdown_values[0]
        if isinstance(dropdown_ref, str) and dropdown_ref.startswith("="):
            raw_ref = dropdown_ref.lstrip("=").replace("'", "")
            ref_sheet_parts = raw_ref.split("!")
            if len(ref_sheet_parts) != 2:
                print(f"Could not parse dropdown range reference: {dropdown_ref}")
                return dropdown_values
            
            ref_sheet, ref_range = ref_sheet_parts
            
            range_query = f"{ref_sheet}!{ref_range}"
            print(f"Fetching dropdown options from range: {range_query}")
            country_resp = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_query
            ).execute()
            return [row[0].strip() for row in country_resp.get("values", []) if row and row[0] and isinstance(row[0], str) and row[0].strip()]
        else: # Hardcoded list
            return [str(v).strip() for v in dropdown_values if str(v).strip()]
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error parsing dropdown at {sheet_name}!{cell}: {e}. Check sheet structure and validation rules.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred in get_dropdown_options for {cell}: {e}")
        return []


def get_alpha_vantage_data(function, symbol, api_key):
    if not api_key:
        print(f"Alpha Vantage API key not available for function {function}, symbol {symbol}.")
        return {}
    url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&apikey={api_key}"
    try:
        response = requests.get(url, timeout=30) # Added timeout
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Alpha Vantage data for {function} ({symbol}): {e}")
        return {}
    except ValueError as e: 
        print(f"Error decoding JSON from Alpha Vantage for {function} ({symbol}): {e}")
        return {}


def get_latest_10k_financials(symbol, api_key):
    print(f"Fetching financial data for {symbol} from Alpha Vantage...")
    overview_data = get_alpha_vantage_data("OVERVIEW", symbol, api_key)
    income_data = get_alpha_vantage_data("INCOME_STATEMENT", symbol, api_key)
    balance_data = get_alpha_vantage_data("BALANCE_SHEET", symbol, api_key)
    quote_data_daily = get_alpha_vantage_data("TIME_SERIES_DAILY", symbol, api_key)

    financials = {}
    try:
        financials["B4"] = overview_data.get("Name", "N/A")
        if financials["B4"] == "N/A":
            print(f"Warning: Could not get company name for {symbol}.")
        
        inc_reports = income_data.get("annualReports", [])
        bal_reports = balance_data.get("annualReports", [])
        price_series = quote_data_daily.get("Time Series (Daily)", {})

        if not inc_reports or len(inc_reports) < 2:
            print(f"Warning: Insufficient annual income reports for {symbol} (found {len(inc_reports)}). Need at least 2.")
            return {"B4": financials["B4"], "error": "Insufficient income data"}
        if not bal_reports or len(bal_reports) < 2:
            print(f"Warning: Insufficient annual balance sheet reports for {symbol} (found {len(bal_reports)}). Need at least 2.")
            return {"B4": financials["B4"], "error": "Insufficient balance sheet data"}
        
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

        date_curr_str = inc_curr.get("fiscalDateEnding")
        date_prev_str = inc_prev.get("fiscalDateEnding")
        if date_curr_str and date_prev_str:
            date_curr = datetime.strptime(date_curr_str, "%Y-%m-%d")
            date_prev = datetime.strptime(date_prev_str, "%Y-%m-%d")
            financials["D11"] = relativedelta(date_curr, date_prev).years
        else:
            financials["D11"] = 1 

        financials["B16"] = "Yes" if safe_float(inc_curr.get("researchAndDevelopment")) > 0 else "No"
        financials["B17"] = "No"

        income_tax_expense = safe_float(inc_curr.get("incomeTaxExpense"))
        pre_tax_income = safe_float(inc_curr.get("incomeBeforeTax", financials["B12"] - financials["B13"])) # incomeBeforeTax or EBIT - Interest
        financials["B23"] = (income_tax_expense / pre_tax_income) if pre_tax_income != 0 else 0.0

        rf_rate_str = overview_data.get("10YearTreasuryRate", "0.04")
        financials["B34"] = safe_float(rf_rate_str, 0.04)
        if financials["B34"] == 0.04 and rf_rate_str != "0.04":
             print(f"Warning: Could not parse 10-Year Treasury Rate '{rf_rate_str}', using default {financials['B34']}.")
        
        print(f"Successfully fetched and processed base financials for {symbol}.")
        return financials

    except KeyError as e:
        print(f"KeyError while processing financial data for {symbol}: {e}. Data might be missing from Alpha Vantage.")
        return {"B4": financials.get("B4", "N/A"), "error": f"Missing key {e}"}
    except IndexError as e:
        print(f"IndexError while processing financial data for {symbol}: {e}. Likely insufficient historical reports.")
        return {"B4": financials.get("B4", "N/A"), "error": f"Insufficient reports {e}"}
    except Exception as e:
        print(f"Unexpected error in get_latest_10k_financials for {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return {"B4": financials.get("B4", "N/A"), "error": f"Unexpected error: {str(e)}"}


def retrieve_date():
    valuation_date = datetime.today()
    return valuation_date.strftime('%b-%d')

def prompt_user_choice(options_list, prompt_message="Please choose an option:"):
    if not options_list:
        print(f"No options provided for: {prompt_message}")
        manual_input = input(f"{prompt_message} (No predefined options, please enter manually): ").strip()
        return manual_input

    print(f"\n{prompt_message}")
    print("You can type part of the name to search for matches, or its number from the list.")
    
    while True:
        search_input = input(f"Search or type number: ").strip()
        matching_options = []

        if search_input.isdigit():
            try:
                choice_idx = int(search_input) -1
                if 0 <= choice_idx < len(options_list):
                    return options_list[choice_idx]
                else:
                    print("Invalid number. Please choose from the list below or type to search.")
            except ValueError:
                pass

        search_term_lower = search_input.lower()
        matching_options = [opt for opt in options_list if search_term_lower in str(opt).lower()]

        if not matching_options:
            print("No matches found. Displaying all options:")
            for idx, opt in enumerate(options_list[:20], start=1):
                print(f"{idx}. {opt}")
            if len(options_list) > 20: print("...and more.")
            continue

        print("\nMatches found:")
        for idx, opt in enumerate(matching_options[:15], start=1):
            print(f"{idx}. {opt}")
        
        if len(matching_options) > 15:
            print(f"...and {len(matching_options) - 15} more matches. Refine your search or choose by number.\n")
        else:
            print("")

        selected_option_input = input("Type your exact choice from the matches above (or number from this filtered list): ").strip()
        
        try: # Try number from filtered list
            choice_idx = int(selected_option_input) -1
            if 0 <= choice_idx < len(matching_options): # Check against current matching_options
                 return matching_options[choice_idx]
        except ValueError:
            pass 

        selected_exact = [opt for opt in matching_options if str(opt).lower() == selected_option_input.lower()]
        
        if selected_exact:
            return selected_exact[0]
        else:
            print("Invalid selection. Please type the exact name or number from the list.\n")

# --- Forecasting Functions ---
def get_annual_financial_data(symbol, api_key, data_type="revenue", history_years=15):
    url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={api_key}"
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        print(f"Request failed for {symbol} income statement (status {response.status_code}).")
        return pd.DataFrame()
    
    data = response.json()
    if "annualReports" not in data or not data["annualReports"]:
        print(f"No annualReports found for symbol {symbol}. Response: {data.get('Information', data.get('Note', 'No further info'))}")
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
                operating_income = safe_float(report.get("operatingIncome", report.get("ebit")))
                total_revenue = safe_float(report.get("totalRevenue"))
                value = (operating_income / total_revenue) * 100 if total_revenue != 0 else 0.0
            
            if value is not None:
                 records.append({"ds": date, "y": value})
        except (KeyError, TypeError, ValueError) as e:
            print(f"Skipping report for {symbol} due to error processing {data_type}: {e} in report: {report.get('fiscalDateEnding')}")
    
    df = pd.DataFrame(records).sort_values("ds").reset_index(drop=True)
    
    if not df.empty:
        cutoff_date = pd.Timestamp.today() - pd.DateOffset(years=history_years)
        df = df[df['ds'] >= cutoff_date]
    
    return df

def forecast_revenue_growth_rate(symbol, api_key, history_years=5, cps_grid=None, plot=True):
    print(f"\nForecasting Revenue Growth Rate for {symbol}...")
    if cps_grid is None: cps_grid = [0.01, 0.05, 0.1, 0.2, 0.3]
    df_revenue = get_annual_financial_data(symbol, api_key, "revenue", history_years)
    
    if len(df_revenue) < 4:
        print(f"Not enough revenue data for Prophet CV for {symbol} (need at least 4 years, got {len(df_revenue)}).")
        if len(df_revenue) >=2: # Basic forecast if at least 2 points
            model = Prophet(yearly_seasonality=False, changepoint_prior_scale=0.05).fit(df_revenue)
            future = model.make_future_dataframe(periods=1, freq='A')
            forecast = model.predict(future)
            last_actual = df_revenue.iloc[-1]["y"]
            next_forecast = forecast.iloc[-1]["yhat"]
            growth_rate = (next_forecast - last_actual) / last_actual if last_actual else 0.0
            if plot: model.plot(forecast); plt.title(f"Revenue Forecast (Simple) for {symbol}"); plt.show()
            return {"growth_rate": growth_rate, "best_cps": 0.05, "error": "Insufficient data for CV, simple forecast used."}
        return {"growth_rate": 0.0, "error": "Insufficient data for any forecast"}

    tuning = []
    days_per_year = 365.25
    n_years_data = len(df_revenue)
    initial_cv_years = min(max(2, n_years_data - 2), n_years_data -1) 
    
    best_cps = 0.05
    if n_years_data >= initial_cv_years + 2:
        for cps in cps_grid:
            m = Prophet(yearly_seasonality=False, changepoint_prior_scale=cps, n_changepoints=min(5, len(df_revenue)-1))
            m.fit(df_revenue)
            try:
                df_cv = cross_validation(m, initial=f"{int(initial_cv_years * days_per_year)} days", period="365 days", horizon="365 days", parallel=None) # None for no parallel
                perf = performance_metrics(df_cv)
                tuning.append({"cps": cps, "mape": perf['mape'].mean()})
            except Exception as e:
                print(f"Prophet CV (Rev Growth) for {symbol} with cps={cps} failed: {e}")
        if tuning: best_cps = min(tuning, key=lambda x: x["mape"])["cps"]
    else:
        print(f"Skipping Prophet CV for {symbol} (Rev Growth) due to limited data ({n_years_data}). Using default CPS.")

    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(5, len(df_revenue)-1))
    model.fit(df_revenue)
    future = model.make_future_dataframe(periods=1, freq='A')
    forecast = model.predict(future)
    
    last_actual_revenue = df_revenue.iloc[-1]["y"]
    next_forecast_revenue = forecast.iloc[-1]["yhat"]
    growth_rate = (next_forecast_revenue - last_actual_revenue) / last_actual_revenue if last_actual_revenue else 0.0
    
    if plot:
        try:
            fig = model.plot(forecast); plt.title(f"Forecasted Revenue for {symbol} (Best CPS: {best_cps:.2f})"); plt.xlabel("Date"); plt.ylabel("Revenue"); plt.tight_layout(); plt.show()
        except Exception as e: print(f"Error plotting revenue forecast for {symbol}: {e}")

    print(f"Revenue Growth Forecast for {symbol}: {growth_rate*100:.2f}% (CPS: {best_cps})")
    return {"growth_rate": growth_rate, "last_actual_revenue": last_actual_revenue, "forecasted_next_year_revenue": next_forecast_revenue, "best_cps": best_cps}

def forecast_operating_margin(symbol, api_key, history_years=10, cps_grid=None, plot=True):
    print(f"\nForecasting Operating Margin for {symbol}...")
    if cps_grid is None: cps_grid = [0.01, 0.05, 0.1, 0.3, 0.5]
    df_margin = get_annual_financial_data(symbol, api_key, "operating_margin", history_years)

    if len(df_margin) < 4:
        print(f"Not enough op margin data for Prophet CV for {symbol} (need at least 4, got {len(df_margin)}).")
        if len(df_margin) >=2:
            model = Prophet(yearly_seasonality=False, changepoint_prior_scale=0.05).fit(df_margin)
            future = model.make_future_dataframe(periods=1, freq='A'); forecast = model.predict(future)
            if plot: model.plot(forecast); plt.title(f"Op Margin Forecast (Simple) for {symbol}"); plt.show()
            return {"margin_forecast": forecast.iloc[-1]['yhat'], "best_cps": 0.05, "error": "Insufficient data for CV, simple forecast used."}
        return {"margin_forecast": 0.0, "error": "Insufficient data for any forecast"}

    best_cps = 0.05; tuning = []
    n_years_data = len(df_margin)
    initial_cv_years = min(max(2, n_years_data - 2), n_years_data -1)

    if n_years_data >= initial_cv_years + 2:
        for cps_val in cps_grid:
            m = Prophet(yearly_seasonality=False, changepoint_prior_scale=cps_val, n_changepoints=min(5, len(df_margin)-1))
            m.fit(df_margin)
            try:
                df_cv = cross_validation(m, initial=f"{int(initial_cv_years * 365.25)} days", period="365 days", horizon="365 days", parallel=None)
                perf = performance_metrics(df_cv)
                tuning.append({'cps': cps_val, 'mape': perf['mape'].mean()})
            except Exception as e: print(f"Prophet CV (Op Margin) for {symbol} with cps={cps_val} failed: {e}")
        if tuning: best_cps = min(tuning, key=lambda x: x['mape'])['cps']
    else:
         print(f"Skipping Prophet CV for {symbol} (Op Margin) due to limited data ({n_years_data}). Using default CPS.")

    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(5, len(df_margin)-1))
    model.fit(df_margin)
    future = model.make_future_dataframe(periods=1, freq='A'); forecast = model.predict(future)
    margin_forecast_val = forecast.iloc[-1]['yhat']
    
    if plot:
        try:
            fig = model.plot(forecast); plt.plot(df_margin['ds'], df_margin['y'], 'o-', label='Historical Margin'); plt.title(f"{symbol} Operating Margin Forecast (Best CPS: {best_cps:.2f})"); plt.xlabel("Year"); plt.ylabel("Operating Margin (%)"); plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()
        except Exception as e: print(f"Error plotting operating margin for {symbol}: {e}")

    print(f"Operating Margin Forecast for {symbol}: {margin_forecast_val:.2f}% (CPS: {best_cps})")
    return {'margin_forecast': margin_forecast_val, 'best_cps': best_cps}

def forecast_revenue_cagr(symbol, api_key, forecast_years=5, history_years=15, cps_grid=None, growth='logistic', plot=True): # Changed default growth to logistic
    print(f"\nForecasting Revenue CAGR for {symbol} over {forecast_years} years (growth: {growth})...")
    if cps_grid is None: cps_grid = [0.05, 0.1, 0.2, 0.3, 0.5]
    df_revenue = get_annual_financial_data(symbol, api_key, "revenue", history_years)

    if len(df_revenue) < 3:
        print(f"Not enough revenue history for CAGR tuning ({symbol}, got {len(df_revenue)}).")
        if len(df_revenue) >=2:
            initial_rev = df_revenue['y'].iloc[0]
            final_rev = df_revenue['y'].iloc[-1]
            num_years_hist = (df_revenue['ds'].iloc[-1].year - df_revenue['ds'].iloc[0].year)
            if num_years_hist > 0 and initial_rev > 0:
                hist_cagr = (final_rev / initial_rev) ** (1/num_years_hist) -1
                return {'cagr_forecast': hist_cagr, 'best_cps': 0.05, 'error': "Insufficient data for Prophet, historical CAGR used."}
        return {'cagr_forecast': 0.0, 'best_cps': 0.05, 'error': "Insufficient data for CAGR"}

    best_cps = 0.05; errors = []
    cap_val = df_revenue['y'].max() * 1.5 if growth == 'logistic' else None
    
    train_df_orig = df_revenue.iloc[:-1].copy()
    if len(train_df_orig) < 2 :
        print(f"Cannot perform CAGR CPS tuning for {symbol} (train data < 2). Using default CPS.")
    else:
        actual_last_year_revenue = df_revenue.iloc[-1]['y']
        for cps_tune_val in cps_grid:
            train_df = train_df_orig.copy()
            model_tune = Prophet(growth=growth, yearly_seasonality=False, changepoint_prior_scale=cps_tune_val, n_changepoints=min(10, len(train_df)-1))
            if growth == 'logistic': train_df['cap'] = cap_val
            
            model_tune.fit(train_df)
            future_tune = model_tune.make_future_dataframe(periods=1, freq='A')
            if growth == 'logistic': future_tune['cap'] = cap_val
            
            forecast_tune = model_tune.predict(future_tune)
            predicted_last_year_revenue = forecast_tune['yhat'].iloc[-1]
            error = np.abs(predicted_last_year_revenue - actual_last_year_revenue) / actual_last_year_revenue if actual_last_year_revenue else float('inf')
            errors.append((cps_tune_val, error))
        if errors: best_cps = min(errors, key=lambda x: x[1])[0]
        print(f"Best CPS for CAGR forecast ({symbol}): {best_cps:.3f}")

    final_model = Prophet(growth=growth, yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(10, len(df_revenue)-1))
    df_revenue_for_fit = df_revenue.copy()
    if growth == 'logistic':
        cap_val_final = df_revenue_for_fit['y'].max() * 1.5 
        df_revenue_for_fit['cap'] = cap_val_final
    
    final_model.fit(df_revenue_for_fit)
    future_final = final_model.make_future_dataframe(periods=forecast_years, freq='A')
    if growth == 'logistic': future_final['cap'] = cap_val_final

    forecast_final = final_model.predict(future_final)
    initial_revenue = df_revenue['y'].iloc[-1]
    forecast_end_revenue = forecast_final['yhat'].iloc[-1]
    cagr_forecast_val = ((forecast_end_revenue / initial_revenue) ** (1/forecast_years) - 1) if initial_revenue and forecast_end_revenue > 0 else 0.0
    
    if plot:
        try:
            fig = final_model.plot(forecast_final); plt.plot(df_revenue['ds'], df_revenue['y'], 'o-', label='Historical Revenue'); plt.title(f"{symbol} {forecast_years}-Yr Revenue Forecast (Best CPS={best_cps:.2f}, Growth: {growth})"); plt.xlabel("Year"); plt.ylabel("Revenue (USD)"); plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()
        except Exception as e: print(f"Error plotting CAGR forecast for {symbol}: {e}")

    print(f"{forecast_years}-Year Forecasted CAGR for {symbol}: {cagr_forecast_val*100:.2f}% (CPS: {best_cps})")
    return {'cagr_forecast': cagr_forecast_val, 'best_cps': best_cps}

def forecast_pretarget_operating_margin(symbol, api_key, history_years=5, plot=True):
    print(f"\nForecasting Pre-Target Operating Margin & Convergence for {symbol}...")
    df_margin = get_annual_financial_data(symbol, api_key, "operating_margin", history_years=max(history_years, 5))

    if len(df_margin) < 2:
        print(f"Not enough historical margin data for trend ({symbol}, got {len(df_margin)}).")
        return {'target_margin': 0.0, 'years_to_converge': np.inf, 'error': "Insufficient data"}

    recent_margins = df_margin.tail(history_years)
    if len(recent_margins) < 2:
        current_margin_val = df_margin['y'].iloc[-1] if not df_margin.empty else 0.0
        print(f"Not enough recent margin data for linear trend ({symbol}). Using last margin as target.")
        return {'current_margin': current_margin_val, 'target_margin': current_margin_val, 'annual_change_pct_points': 0.0, 'years_to_converge': 0.0}

    X = recent_margins['ds'].dt.year.values.reshape(-1, 1)
    y = recent_margins['y'].values

    model = LinearRegression().fit(X, y)
    slope = model.coef_[0]   
    future_year_for_target = X[-1][0] + 5
    target_margin_forecast = model.predict(np.array([[future_year_for_target]]))[0]
    current_margin = y[-1]
    years_to_converge_val = (target_margin_forecast - current_margin) / slope if not np.isclose(slope, 0) else np.inf
    
    if plot:
        try:
            plt.figure(figsize=(10, 6)); plt.plot(recent_margins['ds'].dt.year, y, 'o-', label='Historical Operating Margin (%)'); plt.plot(X, model.predict(X), '--', label='Linear Regression Trend'); plt.axvline(future_year_for_target, color='red', linestyle=':', label=f'Target Year ({future_year_for_target})'); plt.scatter(future_year_for_target, target_margin_forecast, color='red', zorder=5); plt.text(future_year_for_target, target_margin_forecast, f' Target: {target_margin_forecast:.2f}%', va='bottom', ha='right'); plt.title(f'{symbol} Operating Margin Trend & Target'); plt.xlabel('Year'); plt.ylabel('Operating Margin (%)'); plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()
        except Exception as e: print(f"Error plotting pre-target operating margin for {symbol}: {e}")

    print(f"Target Pre-Tax Operating Margin for {symbol} (to {future_year_for_target}): {target_margin_forecast:.2f}%")
    print(f"Years to Converge: {years_to_converge_val:.1f} (Current: {current_margin:.2f}%, Slope: {slope:.2f}%/yr)")
    return {'current_margin': current_margin, 'target_margin': target_margin_forecast, 'annual_change_pct_points': slope, 'years_to_converge': years_to_converge_val}

def forecast_sales_to_capital_ratio(symbol, api_key, history_years=15, cps=0.05, plot=True):
    print(f"\nForecasting Sales-to-Capital Ratio for {symbol}...")
    url_income = f'https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={api_key}'
    try:
        data_income = requests.get(url_income, timeout=30).json()
        if 'annualReports' not in data_income or not data_income['annualReports']:
            print(f"No income statement data for {symbol} for S/C ratio. Info: {data_income.get('Information')}")
            return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "No income data"}
        income_df = pd.DataFrame(data_income['annualReports'])[['fiscalDateEnding', 'totalRevenue']]
        income_df['fiscalDateEnding'] = pd.to_datetime(income_df['fiscalDateEnding'])
        income_df['totalRevenue'] = pd.to_numeric(income_df['totalRevenue'], errors='coerce')
    except Exception as e:
        print(f"Failed to fetch/process income data for S/C ratio ({symbol}): {e}")
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': str(e)}

    url_balance = f'https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={symbol}&apikey={api_key}'
    try:
        data_balance = requests.get(url_balance, timeout=30).json()
        if 'annualReports' not in data_balance or not data_balance['annualReports']:
            print(f"No balance sheet data for {symbol} for S/C ratio. Info: {data_balance.get('Information')}")
            return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "No balance sheet data"}
        balance_df = pd.DataFrame(data_balance['annualReports'])
        balance_df['fiscalDateEnding'] = pd.to_datetime(balance_df['fiscalDateEnding'])
        balance_df['investedCapital'] = pd.to_numeric(balance_df.get('totalAssets'), errors='coerce') # Using totalAssets as proxy
    except Exception as e:
        print(f"Failed to fetch/process balance sheet data for S/C ratio ({symbol}): {e}")
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': str(e)}
        
    df = pd.merge(income_df, balance_df[['fiscalDateEnding', 'investedCapital']], on='fiscalDateEnding', how='inner')
    df.dropna(subset=['totalRevenue', 'investedCapital'], inplace=True)
    df = df.sort_values('fiscalDateEnding')

    cutoff = df['fiscalDateEnding'].max() - pd.DateOffset(years=history_years) if not df.empty else pd.Timestamp.now()
    df = df[df['fiscalDateEnding'] >= cutoff]

    if df.empty or 'investedCapital' not in df.columns or df['investedCapital'].eq(0).all():
        print(f"Not enough valid data for S/C ratio for {symbol} after filtering/merging.")
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "Insufficient merged data"}
        
    df['ratio'] = df['totalRevenue'] / df['investedCapital']
    df_prophet = df[['fiscalDateEnding', 'ratio']].rename(columns={'fiscalDateEnding': 'ds', 'ratio': 'y'})
    
    if len(df_prophet) < 2:
        print(f"Not enough S/C ratio data points for Prophet for {symbol} (got {len(df_prophet)}).")
        avg_hist_ratio = df_prophet['y'].mean() if not df_prophet.empty else 0.0
        return {'avg_1_5': avg_hist_ratio, 'avg_6_10': avg_hist_ratio, 'error': "Insufficient data for forecast, used historical avg."}

    m = Prophet(yearly_seasonality=False, changepoint_prior_scale=cps, n_changepoints=min(5, len(df_prophet)-1))
    m.fit(df_prophet)
    future = m.make_future_dataframe(periods=10, freq='A')
    fc = m.predict(future)

    last_hist_date = df_prophet['ds'].max()
    forecast_points = fc[fc['ds'] > last_hist_date].reset_index(drop=True)

    if len(forecast_points) < 10:
        print(f"Warning: S/C forecast for {symbol} produced {len(forecast_points)} future points (expected 10).")
        if forecast_points.empty:
            avg_hist_ratio = df_prophet['y'].mean() if not df_prophet.empty else 0.0
            return {'avg_1_5': avg_hist_ratio, 'avg_6_10': avg_hist_ratio, 'error': "No future forecast points, used historical avg."}

    avg_1_5_val = forecast_points.loc[0:min(4, len(forecast_points)-1), 'yhat'].mean()
    avg_6_10_val = forecast_points.loc[5:min(9, len(forecast_points)-1), 'yhat'].mean() if len(forecast_points) > 5 else avg_1_5_val

    if plot:
        try:
            fig = m.plot(fc); plt.plot(df_prophet['ds'], df_prophet['y'], 'o-', label='Historical S/C Ratio'); plt.title(f"{symbol} Sales-to-Capital Ratio Forecast (CPS: {cps:.2f})"); plt.xlabel("Year"); plt.ylabel("Sales / Invested Capital"); plt.legend(); plt.grid(True); plt.tight_layout(); plt.show()
        except Exception as e: print(f"Error plotting S/C ratio for {symbol}: {e}")
    
    print(f"Sales-to-Capital (Years 1–5 avg forecast) for {symbol}: {avg_1_5_val:.2f}")
    print(f"Sales-to-Capital (Years 6–10 avg forecast) for {symbol}: {avg_6_10_val:.2f}")
    return {'avg_1_5': avg_1_5_val, 'avg_6_10': avg_6_10_val}

# --- Main Function ---
def run_ginzu_analysis():
    global input_worksheet, valuation_worksheet 

    if not POLYGON_API_KEY or not ALPHA_VANTAGE_API_KEY:
        print("API keys for Polygon or Alpha Vantage are missing. Please set them as environment variables.")
        return

    initialize_google_sheets()

    company_ticker = input("Enter the company ticker (e.g., AAPL): ").strip().upper()
    if not company_ticker:
        print("No ticker entered. Exiting.")
        return

    print(f"\nStarting financial analysis for {company_ticker}...")

    print("\nFetching latest 10-K financials...")
    financials = get_latest_10k_financials(company_ticker, ALPHA_VANTAGE_API_KEY)
    if "error" in financials:
        print(f"Could not fetch initial financials for {company_ticker}: {financials['error']}")
        return
    
    date_val = retrieve_date()
    input_worksheet.update_acell('B3', date_val)
    input_worksheet.update_acell('B4', financials.get("B4", company_ticker))
    print(f"Updated B3 (Date): {date_val}, B4 (Company Name): {financials.get('B4', company_ticker)}")

    country_names = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B7')
    us_industry_names = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B8')
    global_industry_names = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B9')

    country = prompt_user_choice(country_names, "Choose Country of Incorporation:")
    us_industry = prompt_user_choice(us_industry_names, "Choose US Industry:")
    global_industry = prompt_user_choice(global_industry_names, "Choose Global Industry:")

    input_worksheet.update_acell('B7', country)
    input_worksheet.update_acell('B8', us_industry)
    input_worksheet.update_acell('B9', global_industry)
    print(f"Updated B7 (Country): {country}, B8 (US Industry): {us_industry}, B9 (Global Industry): {global_industry}")

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
        'B21': financials.get("B21", 0) / 10000000, 
        'B22': financials.get("B22"),
        'B23': financials.get("B23"), 
        'B24': financials.get("B24"),
        'B34': financials.get("B34") 
    }
    print("\nUpdating base financial data in sheet...")
    for cell, value in financial_updates.items():
        if value is not None:
            input_worksheet.update_acell(cell, value)
        else:
            print(f"Skipped {cell} due to missing value from financials.")
    print("Base financial data updated.")
            
    print("\n--- Generating Forecasts for Value Drivers (will show plots) ---")
    rev_growth_forecast = forecast_revenue_growth_rate(company_ticker, ALPHA_VANTAGE_API_KEY, plot=True)
    suggested_b26_val = rev_growth_forecast.get('growth_rate', 0.0) * 100
    suggested_b26_str = f"{suggested_b26_val:.2f}" if "error" not in rev_growth_forecast else "N/A"
    print(f"Suggested for B26 (Rev Growth Rate Next Yr %): {suggested_b26_str}")

    op_margin_forecast = forecast_operating_margin(company_ticker, ALPHA_VANTAGE_API_KEY, plot=True)
    suggested_b27_val = op_margin_forecast.get('margin_forecast', 0.0)
    suggested_b27_str = f"{suggested_b27_val:.2f}" if "error" not in op_margin_forecast else "N/A"
    print(f"Suggested for B27 (Op Margin Next Yr %): {suggested_b27_str}")

    cagr_forecast = forecast_revenue_cagr(company_ticker, ALPHA_VANTAGE_API_KEY, forecast_years=5, growth='logistic', plot=True)
    suggested_b28_val = cagr_forecast.get('cagr_forecast', 0.0) * 100
    suggested_b28_str = f"{suggested_b28_val:.2f}" if "error" not in cagr_forecast else "N/A"
    print(f"Suggested for B28 (5yr Revenue CAGR %): {suggested_b28_str}")

    pre_target_margin_forecast = forecast_pretarget_operating_margin(company_ticker, ALPHA_VANTAGE_API_KEY, plot=True)
    suggested_b29_val = pre_target_margin_forecast.get('target_margin', 0.0)
    suggested_b29_str = f"{suggested_b29_val:.2f}" if "error" not in pre_target_margin_forecast else "N/A"
    suggested_b30_val = pre_target_margin_forecast.get('years_to_converge', 0.0)
    suggested_b30_str = f"{suggested_b30_val:.1f}" if "error" not in pre_target_margin_forecast else "N/A"
    print(f"Suggested for B29 (Target Pre-Tax Op Margin %): {suggested_b29_str}")
    print(f"Suggested for B30 (Years to Converge Margin): {suggested_b30_str}")

    sc_ratio_forecast = forecast_sales_to_capital_ratio(company_ticker, ALPHA_VANTAGE_API_KEY, plot=True)
    suggested_b31_val = sc_ratio_forecast.get('avg_1_5', 0.0)
    suggested_b31_str = f"{suggested_b31_val:.2f}" if "error" not in sc_ratio_forecast else "N/A"
    suggested_b32_val = sc_ratio_forecast.get('avg_6_10', 0.0)
    suggested_b32_str = f"{suggested_b32_val:.2f}" if "error" not in sc_ratio_forecast else "N/A"
    print(f"Suggested for B31 (Sales/Capital Yrs 1-5): {suggested_b31_str}")
    print(f"Suggested for B32 (Sales/Capital Yrs 6-10): {suggested_b32_str}")

    print("\n--- Please Review Visualizations and Suggested Values Above ---")
    print("Enter your chosen values for the following (press Enter to use suggested value):")

    def get_user_input_for_driver(prompt_text, suggested_value_str, is_percentage=False):
        user_val_str = input(f"{prompt_text} (Suggested: {suggested_value_str}): ").strip()
        if not user_val_str:
            if suggested_value_str == "N/A": return None
            final_val_str = suggested_value_str
        else:
            final_val_str = user_val_str
        
        try:
            numeric_val = float(final_val_str)
            if is_percentage:
                return numeric_val / 100.0
            return numeric_val
        except (ValueError, TypeError):
            print(f"Warning: Could not convert '{final_val_str}' to a number for {prompt_text}. Skipping update for this cell or using raw string if applicable.")
            return final_val_str if not is_percentage else None

    updates_b26_b32 = {
        'B26': get_user_input_for_driver("Revenue growth rate for next year (%)", suggested_b26_str, is_percentage=True),
        'B27': get_user_input_for_driver("Operating margin for next year (%)", suggested_b27_str, is_percentage=True),
        'B28': get_user_input_for_driver("Compounded annual growth rate (CAGR %)", suggested_b28_str, is_percentage=True),
        'B29': get_user_input_for_driver("Target pre-tax operating margin (%)", suggested_b29_str, is_percentage=True),
        'B30': get_user_input_for_driver("Years of convergence for margin", suggested_b30_str),
        'B31': get_user_input_for_driver("Sales to capital ratio (for years 1-5)", suggested_b31_str),
        'B32': get_user_input_for_driver("Sales to capital ratio (for years 6-10)", suggested_b32_str),
    }
    
    print("\nUpdating sheet with your chosen value drivers:")
    for cell, value in updates_b26_b32.items():
        if value is not None:
            try:
                input_worksheet.update_acell(cell, value)
                print(f"Updated {cell}: {value}")
            except Exception as e:
                print(f"Error updating cell {cell} with value {value}: {e}")
        else:
            print(f"Skipped updating {cell} as input was invalid or N/A.")

    print("\n--- Key Valuation Metrics (from 'Valuation' sheet after calculations) ---")
    try:
        print("Pausing for a few seconds for sheet calculations...")
        time.sleep(7) 

        val_b33_str = valuation_worksheet.acell('B33').value
        val_b34_str = valuation_worksheet.acell('B34').value
        val_b35_str = valuation_worksheet.acell('B35').value

        est_value_per_share = safe_float(val_b33_str, default="N/A")
        price_val = safe_float(val_b34_str, default="N/A")
        price_as_percent_val = safe_float(val_b35_str, default="N/A")

        print(f"Estimated value /share: $ {est_value_per_share if isinstance(est_value_per_share, float) else est_value_per_share:.2f}")
        print(f"Price: $ {price_val if isinstance(price_val, float) else price_val:.2f}")
        print(f"Price as % of value: {price_as_percent_val if isinstance(price_as_percent_val, float) else price_as_percent_val:.2f}%")

    except Exception as e:
        print(f"Could not read or format final valuation metrics from sheet: {e}")

    print(f"\nAnalysis for {company_ticker} complete. Check your Google Sheet.")

if __name__ == '__main__':
    run_ginzu_analysis()
