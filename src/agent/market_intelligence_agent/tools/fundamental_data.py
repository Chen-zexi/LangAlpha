from __future__ import annotations
from datetime import date, datetime
from typing import Dict, Any, List, Sequence, Union, Optional
import os
import requests
import csv
from dotenv import load_dotenv
from math import isnan
from statistics import mean
from mcp.server.fastmcp import FastMCP

# Setup
load_dotenv()
API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

if not API_KEY:
    raise EnvironmentError(
        "Missing ALPHA_VANTAGE_API_KEY in environment. "
    )



# Helper functions

def _get(function: str, **params) -> Dict[str, Any]:
    """Call the Alpha Vantage REST endpoint and return the JSON payload."""
    params = {k: v for k, v in params.items() if v is not None}
    params.update({"function": function, "apikey": API_KEY})
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Check for API error messages or notes
    if any(k in data for k in ("Note", "Information", "Error Message")):
        # Consolidate potential messages into one string for the exception
        messages = []
        for key in ("Note", "Information", "Error Message"):
            if key in data and data[key]:
                messages.append(f"{key}: {data[key]}")
        if messages:
            raise RuntimeError(f"Alpha Vantage API message: {'; '.join(messages)}")
    return data

def _num(x: Optional[str]) -> Optional[float]:
    """Convert a string to a float, returning None for empty or invalid strings."""
    try:
        return float(x) if x not in (None, "None", "") else None
    except ValueError:
        return None

def _parse_records(records: List[Dict[str, Any]], fields: List[str]) -> Dict[str, Dict[str, Any]]:
    """Parse a list of records (e.g., annual reports) into a dictionary keyed by fiscal date."""
    parsed: Dict[str, Dict[str, Any]] = {}
    for row in records:
        date = row.get("fiscalDateEnding")
        if not date:
            continue
        entry = parsed.setdefault(date, {})
        for f in fields:
            if f in row:
                entry[f] = _num(row[f])
    return parsed


def _compute_extras(entry: Dict[str, Any]):
    """Add derived financial metrics like Free Cash Flow (FCF) and Net Debt to an entry."""
    ocf = entry.get("operatingCashflow")
    capex = entry.get("capitalExpenditures")
    if ocf is not None and capex is not None:
        entry["freeCashFlow"] = ocf - capex

    cash = entry.get("cashAndShortTermInvestments") or entry.get("cashAndCashEquivalentsAtCarryingValue")
    debt = 0.0
    for dkey in ("longTermDebt", "shortTermDebt"):
        if entry.get(dkey) is not None and not isnan(entry[dkey]): # Ensure value is not NaN
            debt += entry[dkey]

    if cash is not None and not isnan(cash): # Ensure cash is not NaN
        entry["netDebt"] = debt - cash
    elif debt > 0: # If no cash data but debt exists
        entry["netDebt"] = debt
    # If neither cash nor debt data, netDebt will not be set.

def _latest_close(symbol: str) -> Optional[float]:
    """Fetch the latest adjusted closing price for a symbol."""
    try:
        data = _get("TIME_SERIES_DAILY_ADJUSTED", symbol=symbol, outputsize="compact")
        ts = data.get("Time Series (Daily)", {})
        if not ts:
            return None
        latest_date = max(ts.keys()) # Find the most recent date string
        return float(ts[latest_date]["5. adjusted close"])
    except RuntimeError as e:
        print(f"API error fetching latest close for {symbol}: {e}")
        return None
    except (KeyError, ValueError) as e:
        # print(f"Error processing price data for {symbol}: {e}")
        return None

# API Call and Calculation Functions

## Advanced Analytics
def advanced_analytics(
    symbols: Union[str, Sequence[str]],
    *,
    interval: str = "DAILY",
    ohlc: str = "close",
    range: str = '6month',
    calculations: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Fetches fixed-window advanced analytics (multi-ticker)."""
    symbols_param = symbols.upper() if isinstance(symbols, str) else ",".join(s.upper() for s in symbols)
    all_metrics = [
        "MIN", "MAX", "MEAN", "MEDIAN", "CUMULATIVE_RETURN", "VARIANCE",
        "STDDEV", "MAX_DRAWDOWN", "HISTOGRAM", "AUTOCORRELATION",
        "COVARIANCE", "CORRELATION",
    ]
    calcs_param = ",".join(calculations) if calculations else ",".join(all_metrics)
    params: Dict[str, Any] = {
        "SYMBOLS": symbols_param,
        "INTERVAL": interval.upper(),
        "OHLC": ohlc.lower(),
        "CALCULATIONS": calcs_param,
        "RANGE": range # Parameter name is RANGE for the API
    }
    return _get("ANALYTICS_FIXED_WINDOW", **params)

## Earnings
def earnings_calendar(symbol: Optional[str] = None, horizon: str = "3month") -> List[Dict[str, Any]]:
    """Fetches earnings calendar data, optionally for a specific symbol."""
    # Alpha Vantage returns CSV for this endpoint
    base_query_params = f"function=EARNINGS_CALENDAR&horizon={horizon}&apikey={API_KEY}"
    csv_url = f"{BASE_URL}?{base_query_params}"
    if symbol:
        csv_url += f"&symbol={symbol.upper()}"

    try:
        with requests.Session() as s:
            response = s.get(csv_url, timeout=30)
            response.raise_for_status()
            decoded_content = response.content.decode('utf-8')
            
            # Handle potential "Note:" or "Information:" messages in CSV response
            if decoded_content.startswith(("Note:", "Information:", "{", "[")): # Check for JSON error messages too
                try:
                    # Attempt to parse as JSON if it looks like it (common for API limit messages)
                    json_error = requests.utils.to_json(decoded_content)
                    if isinstance(json_error, dict) and ("Note" in json_error or "Information" in json_error or "Error Message" in json_error):
                         raise RuntimeError(f"Alpha Vantage API message: {json_error}")
                except (ValueError, TypeError): # Not a JSON error, might be plain text note in CSV
                     if decoded_content.strip().startswith("Note:") or decoded_content.strip().startswith("Information:"):
                        raise RuntimeError(f"Alpha Vantage API message: {decoded_content.strip()}")
                # If not identifiable as an error, proceed assuming it's CSV data


            csv_reader = csv.DictReader(decoded_content.splitlines())
            json_array = []
            for row in csv_reader:
                # Ensure all expected keys are present, providing defaults if not.
                json_object = {
                    "symbol": row.get("symbol"),
                    "name": row.get("name"),
                    "reportDate": row.get("reportDate"),
                    "fiscalDateEnding": row.get("fiscalDateEnding"),
                    "estimate": _num(row.get("estimate")), # Use _num for safe conversion
                    "currency": row.get("currency")
                }
                json_array.append(json_object)
            return json_array
    except requests.RequestException as e:
        raise RuntimeError(f"Network or API request error for earnings calendar: {e}")
    except RuntimeError as e: # Propagate API message errors
        raise e
    except Exception as e: # Catch other potential errors during CSV processing
        raise RuntimeError(f"Error processing earnings calendar CSV data: {e}")


def earnings_call_transcript(symbol: str, year: int, quarter: int) -> Dict[str, Any]:
    """Fetches earnings call transcript for a given symbol, year, and quarter."""
    if not (1 <= quarter <= 4):
        raise ValueError("Quarter must be between 1 and 4.")
    quarter_param = f"{year}Q{quarter}"
    return _get("EARNINGS_CALL_TRANSCRIPT", symbol=symbol.upper(), quarter=quarter_param)


def company_overview(symbol: str) -> Dict[str, Any]:
    """Fetches company overview data."""
    return _get("OVERVIEW", symbol=symbol.upper())

## Fundamentals
def income_statement(symbol: str, period: str = "annual") -> Dict[str, Any]:
    """Fetches income statement data."""
    if period.lower() not in {"annual", "quarterly"}:
        raise ValueError("period must be 'annual' or 'quarterly'")
    return _get("INCOME_STATEMENT", symbol=symbol.upper(), period=period.lower())


def balance_sheet(symbol: str, period: str = "annual") -> Dict[str, Any]:
    """Fetches balance sheet data."""
    if period.lower() not in {"annual", "quarterly"}:
        raise ValueError("period must be 'annual' or 'quarterly'")
    return _get("BALANCE_SHEET", symbol=symbol.upper(), period=period.lower())


def cash_flow(symbol: str, period: str = "annual") -> Dict[str, Any]:
    """Fetches cash flow statement data."""
    if period.lower() not in {"annual", "quarterly"}:
        raise ValueError("period must be 'annual' or 'quarterly'")
    return _get("CASH_FLOW", symbol=symbol.upper(), period=period.lower())

def earnings(symbol: str) -> Dict[str, Any]:
    """Fetches historical earnings data (EPS)."""
    return _get("EARNINGS", symbol=symbol.upper())

### Merged Fundamental Data
_IS_FIELDS = ["totalRevenue", "operatingIncome", "ebit", "ebitda", "netIncome", "depreciationAndAmortization", "interestExpense", "incomeTaxExpense", "incomeBeforeTax"]
_BS_FIELDS = ["totalAssets", "totalLiabilities", "totalShareholderEquity", "cashAndShortTermInvestments", "cashAndCashEquivalentsAtCarryingValue", "longTermDebt", "shortTermDebt", "commonStockSharesOutstanding"]
_CF_FIELDS = ["operatingCashflow", "capitalExpenditures"]
_ER_ANNUAL_FIELDS = ["reportedEPS"] # Annual earnings usually only have reportedEPS
_ER_QUARTERLY_FIELDS = ["reportedEPS", "estimatedEPS", "surprise", "surprisePercentage"] # Quarterly has more detail

# --- MODIFIED FUNCTION ---
def fundamental_data_from_reports(symbol: str, start_year: int, end_year: int, filings: int = 4) -> Dict[str, Any]:
    """
    Fetches and merges key financial data from Income, Balance Sheet, Cash Flow,
    and Earnings reports.
    Detailed EPS data from the Earnings endpoint is merged into existing annual/quarterly
    reports if a report with the same fiscalDateEnding already exists from IS/BS/CF data.
    This prevents the creation of sparse "annual" reports that only contain EPS.
    """
    if start_year > end_year:
        raise ValueError("Start year must be less than or equal to end year.")

    symbol_upper = symbol.upper()

    # Fetch raw payloads from Alpha Vantage
    try:
        is_payload = income_statement(symbol_upper)
        bs_payload = balance_sheet(symbol_upper)
        cf_payload = cash_flow(symbol_upper)
        er_payload = earnings(symbol_upper) # For EPS data
    except RuntimeError as e:
        print(f"[fundamental_data_from_reports ERROR {symbol_upper}] API call failed during data fetching: {e}")
        return {"symbol": symbol_upper, "annual": [], "quarterly": [], "error": str(e)}


    # --- Annual Data Processing ---
    annual_data: Dict[str, Dict[str, Any]] = {} # Keyed by fiscalDateEnding

    # First, populate with data from Income Statement, Balance Sheet, and Cash Flow
    for payload, fields in [
        (is_payload.get("annualReports", []), _IS_FIELDS),
        (bs_payload.get("annualReports", []), _BS_FIELDS),
        (cf_payload.get("annualReports", []), _CF_FIELDS),
    ]:
        parsed_financial_data = _parse_records(payload, fields)
        for date_key, values in parsed_financial_data.items():
            annual_data.setdefault(date_key, {}).update(values)

    # Second, merge reportedEPS from annualEarnings into EXISTING annual_data entries
    # using _ER_ANNUAL_FIELDS
    parsed_annual_eps = _parse_records(er_payload.get("annualEarnings", []), _ER_ANNUAL_FIELDS)
    merged_eps_count_annual = 0
    for date_key, eps_values in parsed_annual_eps.items():
        if date_key in annual_data:
            annual_data[date_key].update(eps_values)
            merged_eps_count_annual +=1
    # print(f"[fundamental_data_from_reports DEBUG {symbol_upper}] Merged {merged_eps_count_annual} annual EPS records into existing reports.")

    # Filter by year range and add derived metrics (_compute_extras)
    annual_out_list: List[Dict[str, Any]] = []
    for date_key, metrics in annual_data.items():
        try:
            report_year = int(date_key[:4]) 
            if start_year <= report_year <= end_year:
                metrics["fiscalDateEnding"] = date_key 
                _compute_extras(metrics) 
                annual_out_list.append(metrics)
        except (ValueError, TypeError):
            print(f"[fundamental_data_from_reports WARNING {symbol_upper}] Malformed fiscalDateEnding '{date_key}' in annual reports. Skipping entry.")
            continue
    
    annual_out_list.sort(key=lambda x: x["fiscalDateEnding"], reverse=True)

    # --- Quarterly Data Processing (similar logic for merging EPS but with more fields) ---
    quarterly_data: Dict[str, Dict[str, Any]] = {} # Keyed by fiscalDateEnding

    # First, populate with data from Income Statement, Balance Sheet, and Cash Flow
    for payload, fields in [
        (is_payload.get("quarterlyReports", []), _IS_FIELDS),
        (bs_payload.get("quarterlyReports", []), _BS_FIELDS),
        (cf_payload.get("quarterlyReports", []), _CF_FIELDS),
    ]:
        parsed_financial_data = _parse_records(payload, fields)
        for date_key, values in parsed_financial_data.items():
            quarterly_data.setdefault(date_key, {}).update(values)

    # Second, merge detailed earnings data from quarterlyEarnings into EXISTING quarterly_data entries
    # using _ER_QUARTERLY_FIELDS
    parsed_quarterly_earnings_details = _parse_records(er_payload.get("quarterlyEarnings", []), _ER_QUARTERLY_FIELDS)
    merged_earnings_count_quarterly = 0
    for date_key, earnings_detail_values in parsed_quarterly_earnings_details.items():
        if date_key in quarterly_data:  # Only update if a comprehensive report for this date already exists
            quarterly_data[date_key].update(earnings_detail_values)
            merged_earnings_count_quarterly += 1
    # print(f"[fundamental_data_from_reports DEBUG {symbol_upper}] Merged {merged_earnings_count_quarterly} quarterly earnings details into existing reports.")

    # Add derived metrics and sort
    quarterly_out_list: List[Dict[str, Any]] = []
    for date_key, metrics in quarterly_data.items():
        metrics["fiscalDateEnding"] = date_key 
        _compute_extras(metrics)
        quarterly_out_list.append(metrics)
    
    quarterly_out_list.sort(key=lambda x: x["fiscalDateEnding"], reverse=True)
    
    final_quarterly_list = quarterly_out_list[:filings] if filings > 0 else []

    return {
        "symbol": symbol_upper,
        "annual": annual_out_list,
        "quarterly": final_quarterly_list
    }
## Economic Indicators
INDICATOR_CONFIGS = [
    {"id": "REAL_GDP_USA", "av_function": "REAL_GDP", "params": {"interval": "quarterly"}}, # Default is USA
    {"id": "REAL_GDP_PER_CAPITA_USA", "av_function": "REAL_GDP_PER_CAPITA", "params": {}},
    {"id": "TREASURY_YIELD_10Y", "av_function": "TREASURY_YIELD", "params": {"interval": "monthly", "maturity": "10year"}},
    {"id": "FEDERAL_FUNDS_RATE", "av_function": "FEDERAL_FUNDS_RATE", "params": {"interval": "monthly"}},
    {"id": "CPI_USA", "av_function": "CPI", "params": {"interval": "monthly"}}, # Default is USA
    {"id": "INFLATION_USA", "av_function": "INFLATION", "params": {}}, # Default is USA, annual
    {"id": "RETAIL_SALES_USA", "av_function": "RETAIL_SALES", "params": {}}, # Default is USA, monthly
    {"id": "DURABLE_GOODS_ORDERS_USA", "av_function": "DURABLES", "params": {}}, # Default is monthly
    {"id": "UNEMPLOYMENT_RATE_USA", "av_function": "UNEMPLOYMENT", "params": {}}, # Default is monthly
    {"id": "NONFARM_PAYROLL_USA", "av_function": "NONFARM_PAYROLL", "params": {}}, # Default is monthly
]

def fetch_economic_indicators() -> List[Dict[str, Any]]:
    """
    Fetches the latest data point for a predefined list of US economic indicators.
    """
    results: List[Dict[str, Any]] = []
    
    for config in INDICATOR_CONFIGS:
        indicator_id = config["id"]
        av_function_name = config["av_function"]
        params = config["params"]
        
        try:
            api_response = _get(av_function_name, **params)
            
            indicator_name = api_response.get("name", "N/A")
            indicator_unit = api_response.get("unit", "N/A")
            raw_data_points = api_response.get("data")

            if not raw_data_points:
                print(f"Warning [EconIndicator]: No data points found for {indicator_id} ({indicator_name}). Skipping.")
                results.append({
                    "indicatorId": indicator_id,
                    "name": indicator_name,
                    "status": "No data found",
                    "latestDataPoint": {}
                })
                continue
            
            # Data is typically sorted newest to oldest by Alpha Vantage for these endpoints
            latest_point = raw_data_points[0] # Assume first is latest
            date_str = latest_point.get("date")
            value_str = latest_point.get("value")

            if date_str is None or value_str is None:
                print(f"Warning [EconIndicator]: Latest data point for {indicator_id} is malformed. Skipping.")
                results.append({
                    "indicatorId": indicator_id,
                    "name": indicator_name,
                    "status": "Malformed latest data",
                    "latestDataPoint": {}
                })
                continue

            results.append({
                "indicatorId": indicator_id,
                "name": indicator_name,
                "intervalReported": api_response.get("interval", params.get("interval", "N/A")),
                "unit": indicator_unit,
                "latestDataPoint": {
                    "date": date_str,
                    "value": _num(value_str) # Convert value to number
                }
            })
        except RuntimeError as e: # Catch API errors from _get
            print(f"API Error fetching {indicator_id}: {e}")
            results.append({"indicatorId": indicator_id, "name": config.get("av_function"), "status": "API error", "error_message": str(e), "latestDataPoint": {}})
        except Exception as e: # Catch any other unexpected errors
            print(f"Unexpected error processing {indicator_id}: {e}")
            results.append({"indicatorId": indicator_id, "name": config.get("av_function"), "status": "Processing error", "error_message": str(e), "latestDataPoint": {}})
            
    return results


def dcf_valuation(
    symbol: str,
    *,
    # ------------ valuation levers ------------------------------------------
    growth_years:    int   = 5,
    growth_rate:     float | None = None,    # None ⇒ auto-derive
    discount_rate:   float = 0.09,
    terminal_growth: float = 0.03,           # must stay < discount_rate
):
    """
    Single-stage DCF that auto-picks a growth rate:
    1. If caller passes a number → use it.
    2. Else try implied CAGR from Forward P/E and EPS (company_overview).
    3. Else derive historical FCF CAGR from the annual statements.
    Returns a rich dictionary with the inputs, assumptions, and upside %.
    """
    # --- choose statement window -------------------------------------------
    today        = date.today()
    current_year = today.year
    start_year   = current_year - growth_years
    end_year     = current_year

    # --- pull annual statements --------------------------------------------
    rpt = fundamental_data_from_reports(symbol, start_year, end_year)
    annuals = rpt.get("annual", [])
    if not annuals:
        raise RuntimeError(f"No annual statements for {symbol}")

    annuals.sort(key=lambda x: x.get("fiscalDateEnding", ""), reverse=True)
    newest, oldest = annuals[0], annuals[-1]

    # Core fundamentals
    fcf0   = newest.get("freeCashFlow")
    net_cash = -newest.get("netDebt", 0.0)
    shares   = newest.get("commonStockSharesOutstanding")

    if fcf0 is None or fcf0 == 0:
        raise ValueError("Missing or zero freeCashFlow")
    if not shares or shares <= 0:
        raise ValueError("Missing shares outstanding")

    # -----------------------------------------------------------------------
    # 1) Manual override  ·or·  2) Forward P/E  ·or·  3) Historical CAGR
    # -----------------------------------------------------------------------
    growth_source = "override" if growth_rate is not None else None

    if growth_rate is None:
        # —— Try Forward P/E → implied EPS CAGR -----------------------------
        ovw   = company_overview(symbol)
        price = _latest_close(symbol)
        try:
            fwd_pe = float(ovw.get("ForwardPE", ""))
            eps_t  = float(ovw.get("EPS", ""))
            if price and fwd_pe > 0 and eps_t > 0:
                eps_fwd = price / fwd_pe
                years_to_fwd = 2  # FY+2 is common for forward PE
                growth_rate = (eps_fwd / eps_t) ** (1 / years_to_fwd) - 1
                if not (-1 < growth_rate < 3):  # sanity window −100 % … +300 %
                    growth_rate = None
                else:
                    growth_source = "forwardPE"
        except (ValueError, ZeroDivisionError):
            growth_rate = None

    if growth_rate is None:
        # —— Fall back to historical FCF CAGR -------------------------------
        fcf_start = oldest.get("freeCashFlow")
        span_years = max(len(annuals) - 1, 1)
        if fcf_start and fcf_start > 0:
            growth_rate = (fcf0 / fcf_start) ** (1 / span_years) - 1
            growth_source = "historical"
        else:
            growth_rate = 0.20   # last-ditch default
            growth_source = "default20pct"

    # Latest market price
    market_price = _latest_close(symbol)

    if terminal_growth >= discount_rate:
        raise ValueError("terminal_growth must be below discount_rate")

    # ---- explicit FCF PV ---------------------------------------------------
    pv_explicit, fcf_t = 0.0, fcf0
    for t in range(1, growth_years + 1):
        fcf_t *= 1 + growth_rate
        pv_explicit += fcf_t / (1 + discount_rate) ** t

    # ---- terminal value ----------------------------------------------------
    fcf_terminal = fcf_t * (1 + terminal_growth)
    tv  = fcf_terminal / (discount_rate - terminal_growth)
    pv_tv = tv / (1 + discount_rate) ** growth_years

    # ---- equity & per-share -----------------------------------------------
    equity_value        = pv_explicit + pv_tv + net_cash
    intrinsic_per_share = equity_value / shares

    upside_pct = (
        (intrinsic_per_share / market_price - 1) * 100
        if market_price not in (None, 0)
        else None
    )

    # ---- output dictionary -------------------------------------------------
    return {
        "symbol"   : symbol.upper(),
        "asOfDate" : today.isoformat(),
        "assumptions": {
            "growthYears"    : growth_years,
            "growthRateUsed" : round(growth_rate, 4),
            "growthSource"   : growth_source,
            "discountRate"   : discount_rate,
            "terminalGrowth" : terminal_growth,
        },
        "inputs": {
            "trailingFCF"      : fcf0,
            "netCash"          : net_cash,
            "sharesOutstanding": shares,
            "currentPrice"     : market_price,
        },
        "intermediate": {
            "pvOfFCF"           : pv_explicit,
            "terminalValue"     : tv,
            "pvOfTerminalValue" : pv_tv,
            "equityValue"       : equity_value,
        },
        "valuation": {
            "intrinsicValuePerShare": intrinsic_per_share,
            "upsidePercent"         : upside_pct,
        },
    }
    
# Wrapper functions exposed as tools
mcp = FastMCP("AlphaVantageTools")

@mcp.tool()
def get_dcf_valuation(
    symbol: str,
    growth_years: int,
    growth_rate: float = None,
    discount_rate: float = 0.09,
    terminal_growth: float = 0.03
) -> Dict[str, Any]:
    """
    Performs a Discounted Cash Flow (DCF) valuation for a given stock symbol.

    This function automatically determines a suitable growth rate for future
    free cash flows (FCF) based on available data (forward P/E, or historical FCF CAGR if forward P/E is not available)
    You can override the growth rate by passing a number.
    It then projects FCF for a specified number of growth years, calculates their
    present value, estimates a terminal value, and sums these to arrive at an
    intrinsic equity value and per-share value.

    Parameters:
    ----------
    symbol : str
        The stock ticker symbol, Required.
    growth_years : int
        The number of years to project FCF growth explicitly. Required.
    growth_rate : float
        The growth rate to use for the explicit growth period. Optional but recommended for scenario analysis.
        By default, the function will try to calculate a growth rate based on forward P/E.
    discount_rate : float
        The discount rate (Weighted Average Cost of Capital - WACC) to use
        for present value calculations. Optional. Default is 0.09 for 9%.
    terminal_growth : float
        The perpetual growth rate assumed for FCF beyond the explicit growth_years.
        Optional but highly recommended. Default is 0.03 for 3%.

    Returns:
    -------
    Dict[str, Any]
        A dictionary containing the DCF valuation details, including:
        - 'symbol': The stock symbol.
        - 'asOfDate': The date the valuation was performed.
        - 'assumptions': Key assumptions used (growth_years, growthRateUsed, growthSource,
                         discountRate, terminalGrowth).
        - 'inputs': Core financial inputs (trailingFCF, netCash, sharesOutstanding,
                    currentPrice).
        - 'intermediate': Calculated values like pvOfFCF, terminalValue, equityValue.
        - 'valuation': The final intrinsicValuePerShare and upsidePercent compared to
                       the current market price.
    """
    return dcf_valuation(symbol, growth_years=growth_years, growth_rate=growth_rate, discount_rate=discount_rate, terminal_growth=terminal_growth)

@mcp.tool()
def get_fundamental_data(
    symbol: str,
    start_year: int,
    end_year: int,
    quarterly_filings_count: int = 4
) -> Dict[str, Any]:
    """
    Fetches and consolidates fundamental financial data for a company over a specified period.

    Retrieves annual and quarterly data from income statements, balance sheets,
    cash flow statements, and earnings reports. Calculates derived metrics like
    Free Cash Flow (FCF) and Net Debt. Merges earnings details appropriately.

    Parameters:
    ----------
    symbol : str
        The stock ticker symbol (e.g., "AAPL", "MSFT"). Required.
    start_year : int
        The starting year for fetching annual data (inclusive). Required.
    end_year : int
        The ending year for fetching annual data (inclusive). Required. Must be >= start_year.
    quarterly_filings_count : int, optional
        Number of most recent quarterly filings to retrieve (default: 4). Set to 0 for none.

    Returns:
    -------
    Dict[str, Any]
        A dictionary containing the symbol and lists of processed 'annual' and 'quarterly'
        financial reports. Each report in the lists is a dictionary containing various
        financial metrics (Revenue, Net Income, OCF, FCF, Net Debt, EPS, etc.) for that period.
        Returns an 'error' key on failure.
    """
    try:
        # Basic input validation
        if not isinstance(symbol, str) or not symbol.strip():
            return {"error": "Symbol must be a non-empty string.", "symbol": str(symbol)}
        if not isinstance(start_year, int) or not isinstance(end_year, int):
             return {"error": "Start year and end year must be integers.", "symbol": symbol}
        if start_year > end_year:
            return {"error": "Start year cannot be after end year.", "symbol": symbol}
        if not isinstance(quarterly_filings_count, int) or quarterly_filings_count < 0:
            return {"error": "Quarterly filings count must be a non-negative integer.", "symbol": symbol}

        # Call the internal data processing function
        return fundamental_data_from_reports(
            symbol=symbol,
            start_year=start_year,
            end_year=end_year,
            filings=quarterly_filings_count
        )
    except Exception as e:
        # Catch unexpected errors from the underlying function
        return {"error": f"An unexpected error occurred in get_fundamental_data: {str(e)}", "symbol": str(symbol)}


@mcp.tool()
def get_company_overview(symbol: str) -> Dict[str, Any]:
    """
    Retrieves a comprehensive overview of a company from Alpha Vantage.

    Includes details like sector, industry, market capitalization, description,
    financial ratios (P/E, EPS), dividend data, analyst targets, etc.

    Parameters:
    ----------
    symbol : str
        The stock ticker symbol (e.g., "AAPL", "MSFT"). Required.

    Returns:
    -------
    Dict[str, Any]
        A dictionary containing the company overview information as provided by the API.
        Field names generally match the API documentation (e.g., "Symbol", "Name",
        "MarketCapitalization", "PERatio", "Beta"). Numerical values might be strings.
        Returns an 'error' key on failure or if the symbol is not found.
    """
    try:
        # Basic input validation
        if not isinstance(symbol, str) or not symbol.strip():
            return {"error": "Symbol must be a non-empty string.", "symbol": str(symbol)}

        # Call the internal function
        overview_data = company_overview(symbol=symbol)

        # Check for common API error/info messages within the returned dict
        if not overview_data or any(k in overview_data for k in ("Error Message", "Information", "Note")):
             api_message = overview_data.get("Error Message") or overview_data.get("Information") or overview_data.get("Note", "No data returned")
             error_detail = f"API message/error for '{symbol}': {api_message}"
             return {"error": error_detail, "symbol": symbol}

        return overview_data
    except RuntimeError as e: # Catch specific API errors raised by _get
        return {"error": str(e), "symbol": str(symbol)}
    except Exception as e:
        # Catch other unexpected errors
        return {"error": f"An unexpected error occurred in get_company_overview: {str(e)}", "symbol": str(symbol)}


@mcp.tool()
def get_earnings_calendar(symbol: Optional[str] = None, horizon: str = "3month") -> Union[List[Dict[str, Any]], Dict[str, str]]:
    """
    Fetches the upcoming or recent earnings calendar events from Alpha Vantage.

    Can fetch for all companies or filter for a specific symbol.

    Parameters:
    ----------
    symbol : Optional[str], optional
        Stock ticker symbol. If None (default), fetches general calendar.
    horizon : str, optional
        Time horizon ("3month", "6month", "12month"). Default "3month".

    Returns:
    -------
    Union[List[Dict[str, Any]], Dict[str, str]]
        On success: A list of dictionaries, each representing an earnings event with keys
        like 'symbol', 'name', 'reportDate', 'fiscalDateEnding', 'estimate' (EPS), 'currency'.
        On failure: A dictionary containing an 'error' key with a description.
        Returns an empty list if a specific symbol is requested but has no calendar data.
    """
    try:
        # Basic input validation
        if symbol is not None and (not isinstance(symbol, str) or not symbol.strip()):
            return {"error": "If provided, symbol must be a non-empty string."}
        if horizon not in ["3month", "6month", "12month"]:
            return {"error": "Invalid horizon. Must be '3month', '6month', or '12month'."}

        # Call the internal function (which now returns a list or raises RuntimeError)
        return earnings_calendar(symbol=symbol, horizon=horizon)

    except RuntimeError as e: # Catch specific API errors raised by earnings_calendar
        return {"error": str(e), "symbol": str(symbol) if symbol else "N/A"}
    except Exception as e:
        # Catch other unexpected errors
        return {"error": f"An unexpected error occurred in get_earnings_calendar: {str(e)}", "symbol": str(symbol) if symbol else "N/A"}


@mcp.tool()
def get_earnings_call_transcript(symbol: str, year: int, quarter: int) -> Dict[str, Any]:
    """
    Retrieves the earnings call transcript for a specific company, year, and quarter.

    Parameters:
    ----------
    symbol : str
        Stock ticker symbol. Required.
    year : int
        Fiscal year of the earnings call. Required.
    quarter : int
        Fiscal quarter (1, 2, 3, or 4). Required.

    Returns:
    -------
    Dict[str, Any]
        On success: A dictionary containing transcript details, usually with keys like
        'symbol', 'quarter', 'date', and 'transcript' (a list of speaker/speech pairs).
        On failure or if transcript not found: A dictionary containing an 'error' key
        or an API message (e.g., {"Information": "No transcript..."}).
    """
    try:
        # Basic input validation
        if not isinstance(symbol, str) or not symbol.strip():
            return {"error": "Symbol must be a non-empty string.", "symbol": str(symbol)}
        if not isinstance(year, int) or year < 1900 or year > datetime.now().year + 5:
            return {"error": f"Invalid year: {year}. Please provide a realistic fiscal year.", "symbol": symbol}
        if not isinstance(quarter, int) or not (1 <= quarter <= 4):
            return {"error": f"Invalid quarter: {quarter}. Must be an integer between 1 and 4.", "symbol": symbol, "year": year}

        # Call the internal function
        transcript_data = earnings_call_transcript(symbol=symbol, year=year, quarter=quarter)

        # Check for API info messages indicating no data, treat as error for consistency
        if isinstance(transcript_data, dict) and ("Information" in transcript_data or "Note" in transcript_data):
             api_message = transcript_data.get("Information") or transcript_data.get("Note", "No transcript data found.")
             return {"error": f"API message for {symbol} Q{quarter} {year}: {api_message}", "symbol": symbol, "year": year, "quarter": quarter}

        return transcript_data
    except RuntimeError as e: # Catch specific API errors raised by _get
        return {"error": str(e), "symbol": str(symbol), "year": year, "quarter": quarter}
    except ValueError as e: # Catch specific validation errors from earnings_call_transcript
        return {"error": str(e), "symbol": str(symbol), "year": year, "quarter": quarter}
    except Exception as e:
        # Catch other unexpected errors
        return {"error": f"An unexpected error occurred: {str(e)}", "symbol": str(symbol), "year": year, "quarter": quarter}


@mcp.tool()
def get_advanced_analytics_metrics(
    symbols: Union[str, Sequence[str]],
    interval: str = "DAILY",
    ohlc_field: str = "close",
    data_range: str = '6month',
    calculations: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Fetches advanced financial analytics for one or more stock symbols.

    Calculates metrics like min/max price, mean, standard deviation, cumulative return,
    max drawdown, covariance, correlation, etc., based on historical price data.

    Parameters:
    ----------
    symbols : Union[str, Sequence[str]]
        Single symbol string or list/tuple of symbols. Required.
    interval : str, optional
        Time interval ("1min", "DAILY", etc.). Default "DAILY".
    ohlc_field : str, optional
        Price field ("open", "high", "low", "close"). Default "close".
    data_range : str, optional
        Historical data range ('6month', '1year', etc.). Default '6month'.
    calculations : Optional[Sequence[str]], optional
        Specific metrics to calculate (e.g., ["MEAN", "STDDEV"]). Default all available.

    Returns:
    -------
    Dict[str, Any]
        On success: A dictionary containing analytics results, typically nested under
        'metadata' and 'payload' keys. The 'payload' structure depends on the symbols
        and calculations requested (e.g., per-symbol results, correlation matrix).
        On failure: A dictionary containing an 'error' key.
    """
    try:
        # Basic input validation
        if not symbols:
            return {"error": "Symbols parameter cannot be empty."}
        if isinstance(symbols, str) and not symbols.strip():
            return {"error": "Symbol string cannot be empty."}
        if isinstance(symbols, (list, tuple)) and not all(isinstance(s, str) and s.strip() for s in symbols):
             return {"error": "All symbols in a list must be non-empty strings."}

        # Call the internal function
        return advanced_analytics(
            symbols=symbols,
            interval=interval,
            ohlc=ohlc_field,
            range=data_range,
            calculations=calculations
        )
    except RuntimeError as e: # Catch specific API errors raised by _get
        return {"error": str(e), "symbols_requested": symbols}
    except Exception as e:
        # Catch other unexpected errors
        return {"error": f"An unexpected error occurred in get_advanced_analytics_metrics: {str(e)}", "symbols_requested": symbols}


@mcp.tool()
def get_latest_economic_indicators() -> Union[List[Dict[str, Any]], Dict[str,str]]:
    """
    Fetches latest data points for a predefined list of key U.S. economic indicators.

    Includes indicators like GDP, Treasury Yields, Fed Funds Rate, CPI, Inflation,
    Retail Sales, Unemployment, Nonfarm Payroll, etc.

    Parameters:
    ----------
    None.

    Returns:
    -------
    Union[List[Dict[str, Any]], Dict[str,str]]
        On success: A list of dictionaries, each representing an indicator. Includes keys like
        'indicatorId', 'name', 'intervalReported', 'unit', 'latestDataPoint' (with 'date' and 'value'),
        and a 'status' ("Success", "No data found", "API error", etc.).
        On general failure: A dictionary containing an 'error' key. Individual indicator
        fetch errors are noted within the list items via the 'status' and 'error_message' keys.
    """
    try:
        # Call the internal function
        return fetch_economic_indicators()
    except Exception as e:
        # Catch unexpected errors from the underlying function
        return {"error": f"An unexpected error occurred while fetching economic indicators: {str(e)}"}


# __all__ can be useful for `from module import *` but less critical for tool-based exposure
__all__: List[str] = [
    "calculate_dcf",
    "fundamental_data_from_reports",
    "company_overview",
    "earnings_calendar",
    "earnings_call_transcript",
    "advanced_analytics",
    "fetch_economic_indicators",
    "income_statement", "balance_sheet", "cash_flow", "earnings" # Exposing base data functions too
]

if __name__ == "__main__":
    mcp.run(transport="stdio")