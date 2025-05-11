import sys
import warnings
import time
import traceback # Keep for final exception handling if needed

from config import POLYGON_API_KEY, ALPHA_VANTAGE_API_KEY, SPREADSHEET_ID, INPUT_SHEET_NAME
from google_sheets import initialize_google_sheets, get_dropdown_options
import google_sheets as gs_manager 
from data_providers import get_latest_10k_financials # get_related_tickers is not used in run_ginzu_analysis
from forecasting import (
    forecast_revenue_growth_rate, forecast_operating_margin, forecast_revenue_cagr, 
    forecast_pretarget_operating_margin, forecast_sales_to_capital_ratio
)
from utils import retrieve_date, prompt_user_choice, safe_float

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Main Function (Interactive Script Version) ---
def run_ginzu_analysis():
    """
    Runs the interactive Ginzu financial analysis script.
    """
    # Global worksheet objects are now accessed via gs_manager
    # and will be populated by initialize_google_sheets()

    if not POLYGON_API_KEY or not ALPHA_VANTAGE_API_KEY:
        print("API keys for Polygon or Alpha Vantage are missing. Please set them in your .env file.")
        return

    initialize_google_sheets() # Ensures sheets are ready, exits on failure

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
    # Ensure input_worksheet is available after initialization
    if not gs_manager.input_worksheet:
        print("Error: Input worksheet not initialized. Exiting.")
        return
        
    gs_manager.input_worksheet.update_acell('B3', date_val)
    gs_manager.input_worksheet.update_acell('B4', financials.get("B4", company_ticker))
    print(f"Updated B3 (Date): {date_val}, B4 (Company Name): {financials.get('B4', company_ticker)}")

    country_names = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B7')
    us_industry_names = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B8')
    global_industry_names = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B9')

    country = prompt_user_choice(country_names, "Choose Country of Incorporation:")
    us_industry = prompt_user_choice(us_industry_names, "Choose US Industry:")
    global_industry = prompt_user_choice(global_industry_names, "Choose Global Industry:")

    gs_manager.input_worksheet.update_acell('B7', country)
    gs_manager.input_worksheet.update_acell('B8', us_industry)
    gs_manager.input_worksheet.update_acell('B9', global_industry)
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
        'B21': financials.get("B21", 0) / 10000000, # Shares in millions
        'B22': financials.get("B22"), # Current Stock Price
        'B23': financials.get("B23"), # Effective Tax Rate
        'B24': financials.get("B24"), # Marginal Tax Rate
        'B34': financials.get("B34")  # Risk-free rate for cell B34
    }
    print("\nUpdating base financial data in sheet...")
    for cell, value in financial_updates.items():
        if value is not None:
            gs_manager.input_worksheet.update_acell(cell, value)
        else:
            print(f"Skipped updating {cell} due to missing value from financials.")
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
        final_val_str_to_convert = suggested_value_str if not user_val_str else user_val_str
        if final_val_str_to_convert == "N/A": return None 
        try:
            numeric_val = float(final_val_str_to_convert)
            return numeric_val / 100.0 if is_percentage else numeric_val
        except (ValueError, TypeError):
            print(f"Warning: Could not convert '{final_val_str_to_convert}' to a number for {prompt_text}.")
            return final_val_str_to_convert if not is_percentage and isinstance(final_val_str_to_convert, str) else None

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
                gs_manager.input_worksheet.update_acell(cell, value)
                print(f"Updated {cell}: {value}")
            except Exception as e:
                print(f"Error updating cell {cell} with value {value}: {e}")
        else:
            print(f"Skipped updating {cell} as input was invalid or N/A.")

    print("\n--- Key Valuation Metrics (from 'Valuation' sheet after calculations) ---")
    try:
        print("Pausing for a few seconds for sheet calculations...")
        time.sleep(7) 
        
        # Ensure valuation_worksheet is available
        if not gs_manager.valuation_worksheet:
            print("Error: Valuation worksheet not initialized. Cannot fetch metrics.")
            return

        val_b33_str = gs_manager.valuation_worksheet.acell('B33').value
        val_b34_str = gs_manager.valuation_worksheet.acell('B34').value
        val_b35_str = gs_manager.valuation_worksheet.acell('B35').value

        est_value_num = safe_float(val_b33_str, default=None) 
        price_num = safe_float(val_b34_str, default=None)
        perc_val_num = None
        if isinstance(val_b35_str, str):
            cleaned_b35 = val_b35_str.replace('%', '').replace(',', '')
            perc_val_num = safe_float(cleaned_b35, default=None)
        elif val_b35_str is not None:
            perc_val_num = safe_float(val_b35_str, default=None)

        if est_value_num is not None: print(f"Estimated value /share: $ {est_value_num:.2f}")
        else: print(f"Estimated value /share: {val_b33_str if val_b33_str is not None else 'N/A'}")

        if price_num is not None: print(f"Price: $ {price_num:.2f}")
        else: print(f"Price: {val_b34_str if val_b34_str is not None else 'N/A'}")

        if perc_val_num is not None: print(f"Price as % of value: {perc_val_num:.2f}%")
        else: print(f"Price as % of value: {val_b35_str if val_b35_str is not None else 'N/A'}")

    except Exception as e:
        print(f"Could not read or format final valuation metrics from sheet: {e}")
        traceback.print_exc()

    print(f"\nAnalysis for {company_ticker} complete. Check your Google Sheet.")

if __name__ == '__main__':
    run_ginzu_analysis()
