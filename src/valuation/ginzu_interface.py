import sys
import warnings
import time
import traceback # Keep for final exception handling if needed
from typing import Dict, Optional, Any # Added for type hinting
import logging # Added for logging in the new function
import asyncio # For wrapping sync calls if needed

from .config import POLYGON_API_KEY, ALPHA_VANTAGE_API_KEY, SPREADSHEET_ID, INPUT_SHEET_NAME
from .google_sheets import initialize_google_sheets, get_dropdown_options
from . import google_sheets as gs_manager
from .data_providers import get_latest_10k_financials # get_related_tickers is not used in run_ginzu_analysis
from .forecasting import (
    forecast_revenue_growth_rate, forecast_operating_margin, forecast_revenue_cagr, 
    forecast_pretarget_operating_margin, forecast_sales_to_capital_ratio
)
from .utils import retrieve_date, prompt_user_choice, safe_float

warnings.filterwarnings("ignore", category=FutureWarning)

# --- New API-callable Function for Initial Suggestions --- (Moved and renamed for clarity)
async def get_initial_analysis_suggestions(
    company_ticker: str,
    country: str,
    us_industry: str,
    global_industry: str
) -> Dict[str, Any]:
    """
    Fetches initial analysis suggestions including company info, suggested financial metrics,
    and base64 encoded plots. Does NOT update Google Sheets at this stage.

    Assumption: Forecasting functions in forecasting.py, when called with plot=True,
    will return a dict including a 'plot_base64' key with the image data.
    """
    logger = logging.getLogger(__name__) # Added logger
    logger.info(f"Fetching initial analysis suggestions for {company_ticker}.")
    results: Dict[str, Any] = {
        "company_name": None,
        "ticker": company_ticker.strip().upper(),
        "b26_rev_growth_suggested_pct": None,
        "b26_rev_growth_plot_base64": None,
        "b27_op_margin_suggested_pct": None,
        "b27_op_margin_plot_base64": None,
        "b28_cagr_suggested_pct": None,
        "b28_cagr_plot_base64": None,
        "b29_target_op_margin_suggested_pct": None,
        "b29_target_op_margin_plot_base64": None,
        "b30_years_to_converge_suggested": None,
        "b31_sc_ratio_1_5_suggested": None,
        "b32_sc_ratio_6_10_suggested": None,
        "b31_sc_ratio_plot_base64": None,
        "error": None,
        "message": None
    }

    if not POLYGON_API_KEY or not ALPHA_VANTAGE_API_KEY:
        results["error"] = "API keys for Polygon or Alpha Vantage are missing."
        logger.error(results["error"])
        return results

    try:
        # 1. Fetch basic company financials/info (name, etc.)
        # You might want a lightweight version or just specific fields from get_latest_10k_financials
        # For now, let's assume it fetches the company name correctly.
        logger.info(f"Fetching basic financials for {results['ticker']} for suggestions...")
        financials = await asyncio.to_thread(get_latest_10k_financials, results['ticker'], ALPHA_VANTAGE_API_KEY)
        if "error" in financials:
            results["error"] = f"Could not fetch basic info for {results['ticker']}: {financials['error']}"
            logger.error(results["error"])
            return results
        results["company_name"] = financials.get("B4", results['ticker']) # B4 is company name from previous observation

        # 2. Generate Forecasts WITH PLOTS
        logger.info(f"Generating forecasts with plots for {results['ticker']}...")

        # B26: Revenue Growth Rate Next Year (%)
        # Assuming forecast_revenue_growth_rate is made async or wrapped
        rev_growth_forecast = await asyncio.to_thread(forecast_revenue_growth_rate, results['ticker'], ALPHA_VANTAGE_API_KEY, plot=True)
        results["b26_rev_growth_suggested_pct"] = rev_growth_forecast.get('growth_rate', 0.0) * 100
        results["b26_rev_growth_plot_base64"] = rev_growth_forecast.get('plot_base64')
        logger.info(f"Revenue growth forecast complete. Plot available: {results['b26_rev_growth_plot_base64'] is not None}")

        # B27: Operating Margin Next Year (%)
        op_margin_forecast = await asyncio.to_thread(forecast_operating_margin, results['ticker'], ALPHA_VANTAGE_API_KEY, plot=True)
        results["b27_op_margin_suggested_pct"] = op_margin_forecast.get('margin_forecast', 0.0)
        results["b27_op_margin_plot_base64"] = op_margin_forecast.get('plot_base64')
        logger.info(f"Operating margin forecast complete. Plot available: {results['b27_op_margin_plot_base64'] is not None}")

        # B28: 5-Year Revenue CAGR (%)
        cagr_forecast = await asyncio.to_thread(forecast_revenue_cagr, results['ticker'], ALPHA_VANTAGE_API_KEY, forecast_years=5, growth='logistic', plot=True)
        results["b28_cagr_suggested_pct"] = cagr_forecast.get('cagr_forecast', 0.0) * 100
        results["b28_cagr_plot_base64"] = cagr_forecast.get('plot_base64')
        logger.info(f"CAGR forecast complete. Plot available: {results['b28_cagr_plot_base64'] is not None}")

        # B29 & B30: Target Operating Margin & Years to Converge
        pre_target_margin_forecast = await asyncio.to_thread(forecast_pretarget_operating_margin, results['ticker'], ALPHA_VANTAGE_API_KEY, plot=True)
        results["b29_target_op_margin_suggested_pct"] = pre_target_margin_forecast.get('target_margin', 0.0)
        results["b30_years_to_converge_suggested"] = pre_target_margin_forecast.get('years_to_converge', 0.0)
        results["b29_target_op_margin_plot_base64"] = pre_target_margin_forecast.get('plot_base64')
        logger.info(f"Target margin forecast complete. Plot available: {results['b29_target_op_margin_plot_base64'] is not None}")

        # B31 & B32: Sales to Capital Ratio (Years 1-5 and 6-10)
        sc_ratio_forecast = await asyncio.to_thread(forecast_sales_to_capital_ratio, results['ticker'], ALPHA_VANTAGE_API_KEY, plot=True)
        results["b31_sc_ratio_1_5_suggested"] = sc_ratio_forecast.get('avg_1_5', 0.0)
        results["b32_sc_ratio_6_10_suggested"] = sc_ratio_forecast.get('avg_6_10', 0.0)
        results["b31_sc_ratio_plot_base64"] = sc_ratio_forecast.get('plot_base64')
        logger.info(f"S/C ratio forecast complete. Plot available: {results['b31_sc_ratio_plot_base64'] is not None}")

        # Success message
        results["message"] = f"Initial analysis for {results['ticker']} completed successfully."
        return results

    except Exception as e:
        logger.error(f"Error in get_initial_analysis_suggestions for {company_ticker}: {str(e)}", exc_info=True)
        results["error"] = f"Failed to generate analysis suggestions: {str(e)}"
        results["message"] = "An error occurred during analysis."
        return results

# --- Existing API-callable Function for Full Analysis (Finalize) ---
def run_ginzu_analysis_for_api(
    company_ticker: str,
    country: str,
    us_industry: str,
    global_industry: str,
    revenue_growth_rate_next_year: Optional[float] = None,
    operating_margin_next_year: Optional[float] = None,
    cagr_5yr_revenue: Optional[float] = None,
    target_pre_tax_operating_margin: Optional[float] = None,
    years_to_converge_margin: Optional[float] = None,
    sales_to_capital_ratio_yrs_1_5: Optional[float] = None,
    sales_to_capital_ratio_yrs_6_10: Optional[float] = None
) -> Dict[str, Any]:
    """
    Runs the Ginzu financial analysis non-interactively for API calls.
    Accepts all necessary inputs as parameters.
    Values for forecast drivers (e.g., revenue_growth_rate_next_year) are expected as percentages (e.g., 5.0 for 5%).
    """
    results: Dict[str, Any] = {
        "message": None,
        "estimated_value_per_share": None,
        "price": None,
        "price_as_percentage_of_value": None,
        "error": None
    }

    if not POLYGON_API_KEY or not ALPHA_VANTAGE_API_KEY:
        results["error"] = "API keys for Polygon or Alpha Vantage are missing."
        return results

    try:
        initialize_google_sheets() # Ensures sheets are ready
        if not gs_manager.input_worksheet or not gs_manager.valuation_worksheet:
            results["error"] = "Google Sheets worksheets not initialized correctly."
            return results
    except Exception as e:
        results["error"] = f"Failed to initialize Google Sheets: {str(e)}"
        return results

    if not company_ticker:
        results["error"] = "No ticker provided."
        return results
    
    company_ticker = company_ticker.strip().upper()
    print(f"Starting API financial analysis for {company_ticker}...") # Keep print for server logs

    try:
        print("Fetching latest 10-K financials for API...")
        financials = get_latest_10k_financials(company_ticker, ALPHA_VANTAGE_API_KEY)
        if "error" in financials:
            results["error"] = f"Could not fetch initial financials for {company_ticker}: {financials['error']}"
            return results
        
        date_val = retrieve_date()
        gs_manager.input_worksheet.update_acell('B3', date_val)
        gs_manager.input_worksheet.update_acell('B4', financials.get("B4", company_ticker))
        print(f"Updated B3 (Date): {date_val}, B4 (Company Name): {financials.get('B4', company_ticker)}")

        # Use provided country and industry data
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
        print("Updating base financial data in sheet for API...")
        for cell, value in financial_updates.items():
            if value is not None:
                gs_manager.input_worksheet.update_acell(cell, value)
            else:
                print(f"Skipped updating {cell} due to missing value from financials.")
        print("Base financial data updated for API.")
                
        print("--- Generating Forecasts for Value Drivers (no plots for API) ---")
        # Forecasts (plot=False for API)
        rev_growth_forecast = forecast_revenue_growth_rate(company_ticker, ALPHA_VANTAGE_API_KEY, plot=False)
        suggested_b26_val = rev_growth_forecast.get('growth_rate', 0.0) * 100 # As percentage

        op_margin_forecast = forecast_operating_margin(company_ticker, ALPHA_VANTAGE_API_KEY, plot=False)
        suggested_b27_val = op_margin_forecast.get('margin_forecast', 0.0) # Already a percentage from function

        cagr_forecast = forecast_revenue_cagr(company_ticker, ALPHA_VANTAGE_API_KEY, forecast_years=5, growth='logistic', plot=False)
        suggested_b28_val = cagr_forecast.get('cagr_forecast', 0.0) * 100 # As percentage

        pre_target_margin_forecast = forecast_pretarget_operating_margin(company_ticker, ALPHA_VANTAGE_API_KEY, plot=False)
        suggested_b29_val = pre_target_margin_forecast.get('target_margin', 0.0) # Already a percentage
        suggested_b30_val = pre_target_margin_forecast.get('years_to_converge', 0.0)

        sc_ratio_forecast = forecast_sales_to_capital_ratio(company_ticker, ALPHA_VANTAGE_API_KEY, plot=False)
        suggested_b31_val = sc_ratio_forecast.get('avg_1_5', 0.0)
        suggested_b32_val = sc_ratio_forecast.get('avg_6_10', 0.0)

        # Determine values for B26-B32: use provided or suggested
        # Input values are percentages (e.g. 5.0 for 5%), convert to decimal for sheet update if needed by gs_manager
        # The original script's `get_user_input_for_driver` converted percentages to decimal (value / 100.0)
        # So, values stored in sheet should be decimal for percentages.

        final_b26 = (revenue_growth_rate_next_year / 100.0) if revenue_growth_rate_next_year is not None else (suggested_b26_val / 100.0 if suggested_b26_val != "N/A" else None)
        final_b27 = (operating_margin_next_year / 100.0) if operating_margin_next_year is not None else (suggested_b27_val / 100.0 if suggested_b27_val != "N/A" else None)
        final_b28 = (cagr_5yr_revenue / 100.0) if cagr_5yr_revenue is not None else (suggested_b28_val / 100.0 if suggested_b28_val != "N/A" else None)
        final_b29 = (target_pre_tax_operating_margin / 100.0) if target_pre_tax_operating_margin is not None else (suggested_b29_val / 100.0 if suggested_b29_val != "N/A" else None)
        final_b30 = years_to_converge_margin if years_to_converge_margin is not None else (suggested_b30_val if suggested_b30_val != "N/A" else None)
        final_b31 = sales_to_capital_ratio_yrs_1_5 if sales_to_capital_ratio_yrs_1_5 is not None else (suggested_b31_val if suggested_b31_val != "N/A" else None)
        final_b32 = sales_to_capital_ratio_yrs_6_10 if sales_to_capital_ratio_yrs_6_10 is not None else (suggested_b32_val if suggested_b32_val != "N/A" else None)
        
        updates_b26_b32 = {
            'B26': final_b26, 'B27': final_b27, 'B28': final_b28,
            'B29': final_b29, 'B30': final_b30, 'B31': final_b31, 'B32': final_b32,
        }
        
        print("Updating sheet with value drivers for API:")
        for cell, value in updates_b26_b32.items():
            if value is not None: 
                try:
                    gs_manager.input_worksheet.update_acell(cell, value)
                    print(f"Updated {cell}: {value}")
                except Exception as e:
                    print(f"Error updating cell {cell} with value {value}: {e}") # Log and continue
            else:
                print(f"Skipped updating {cell} as value was None or N/A.")

        print("Pausing for sheet calculations (API)...")
        
        val_b33_str = gs_manager.valuation_worksheet.acell('B33').value
        val_b34_str = gs_manager.valuation_worksheet.acell('B34').value
        val_b35_str = gs_manager.valuation_worksheet.acell('B35').value
        print(f"DEBUG GINZU: Raw val_b35_str from sheet: '{val_b35_str}' (type: {type(val_b35_str)})")

        # Clean currency symbols before converting to float
        if isinstance(val_b33_str, str):
            val_b33_str = val_b33_str.replace('$', '').replace(',', '')
        if isinstance(val_b34_str, str):
            val_b34_str = val_b34_str.replace('$', '').replace(',', '')

        results["estimated_value_per_share"] = safe_float(val_b33_str)
        results["price"] = safe_float(val_b34_str)
        
        # Ensure B35 is processed into a float or None
        perc_val_num = None
        if isinstance(val_b35_str, str):
            cleaned_b35 = val_b35_str.replace('%', '').replace(',', '') # Remove % and ,
            print(f"DEBUG GINZU: cleaned_b35 for B35: '{cleaned_b35}' (type: {type(cleaned_b35)})")
            perc_val_num = safe_float(cleaned_b35, default=None)       # Convert to float
            print(f"DEBUG GINZU: perc_val_num after safe_float on string: {perc_val_num} (type: {type(perc_val_num)})")
        elif val_b35_str is not None: # If it's already a number from the sheet
             perc_val_num = safe_float(val_b35_str, default=None)   # Ensure it's a float or None
             print(f"DEBUG GINZU: perc_val_num after safe_float on non-string: {perc_val_num} (type: {type(perc_val_num)})")
        else: # val_b35_str was None
            print(f"DEBUG GINZU: val_b35_str is None, perc_val_num remains None.")

        # Ensure price_as_percentage_of_value is never None
        results["price_as_percentage_of_value"] = perc_val_num if perc_val_num is not None else 0.0

        results["message"] = f"Analysis for {company_ticker} complete."
        print(f"API Analysis for {company_ticker} complete.")

    except Exception as e:
        print(f"Error during Ginzu API analysis for {company_ticker}: {e}")
        traceback.print_exc()
        results["error"] = f"An error occurred during analysis: {str(e)}"
        # Ensure default values for required fields
        results["estimated_value_per_share"] = None if results["estimated_value_per_share"] is None else results["estimated_value_per_share"]
        results["price"] = None if results["price"] is None else results["price"]
        results["price_as_percentage_of_value"] = 0.0 if results["price_as_percentage_of_value"] is None else results["price_as_percentage_of_value"]

    return results

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

        # Clean currency symbols before converting to float
        if isinstance(val_b33_str, str):
            val_b33_str = val_b33_str.replace('$', '').replace(',', '')
        if isinstance(val_b34_str, str):
            val_b34_str = val_b34_str.replace('$', '').replace(',', '')

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
