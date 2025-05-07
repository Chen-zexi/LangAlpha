from __future__ import annotations
from typing import Dict, Any, List, Sequence, Union, Optional
import os
import requests
import pandas as pd
import csv
from dotenv import load_dotenv
from math import isnan
from mcp.server.fastmcp import FastMCP

# Setup
load_dotenv()
API_KEY: str | None = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

if not API_KEY:
    raise EnvironmentError(
        "Missing ALPHAVANTAGE_API_KEY in environment. "
        "Create a .env file with `ALPHAVANTAGE_API_KEY=<your‑key>`."
    )

# Helper functions
def _get(function: str, **params) -> Dict[str, Any]:
    """Call the Alpha Vantage REST endpoint and return the JSON payload."""
    params = {k: v for k, v in params.items() if v is not None}
    params.update({"function": function, "apikey": API_KEY})
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if any(k in data for k in ("Note", "Information", "Error Message")):
        raise RuntimeError(f"Alpha Vantage API message: {data}")
    return data

def _num(x: Optional[str]) -> Optional[float]:
    try:
        return float(x) if x not in (None, "None", "") else None
    except ValueError:
        return None

def _parse_records(records: List[Dict[str, Any]], fields: List[str]) -> Dict[str, Dict[str, Any]]:
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
    """Add derived metrics used in valuation (FCF, net debt)."""
    ocf = entry.get("operatingCashflow")
    capex = entry.get("capitalExpenditures")
    if ocf is not None and capex is not None:
        entry["freeCashFlow"] = ocf - capex

    cash = entry.get("cashAndShortTermInvestments") or entry.get("cashAndCashEquivalentsAtCarryingValue")
    debt = 0.0
    for dkey in ("longTermDebt", "shortTermDebt"):
        if entry.get(dkey) is not None:
            debt += entry[dkey]
    if cash is not None:
        entry["netDebt"] = debt - cash
    elif debt:
        entry["netDebt"] = debt

# API Calls

## Advanced Analytics

def advanced_analytics(
    symbols: Union[str, Sequence[str]],
    *,
    interval: str = "DAILY",
    ohlc: str = "close",
    range: str = '6month',
    calculations: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Fixed-window advanced analytics (multi-ticker).

    Parameters
    ----------
    symbols : str | Sequence[str]
        One ticker or a sequence (≤5 on). 
    interval : str, default "DAILY"
        Sampling interval (`1min`, `5min`, `60min`, `DAILY`, `WEEKLY`, `MONTHLY`, …).
    ohlc : str, default "close"
        Price field for return calculation (`open`, `high`, `low`, `close`).
    range_ : str, default '6month'
        The range of data to return, can be '{N}day', '{N}week', '{N}month', '{N}year'. 
    calculations : Sequence[str] | None
        List of metric specifiers (`"MIN", "MAX", "MEAN", "MEDIAN", "CUMULATIVE_RETURN", "VARIANCE",
        "STDDEV", "MAX_DRAWDOWN", "HISTOGRAM", "AUTOCORRELATION",
        "COVARIANCE", "CORRELATION"`).
        When *None*, **all** available metrics are requested.

    Returns
    -------
    dict
        Raw JSON payload from Alpha Vantage.
    """
    if isinstance(symbols, str):
        symbols_param = symbols.upper()
    else:
        symbols_param = ",".join(s.upper() for s in symbols)

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
    }

    if range:
        # requests supports repeating keys by using a list value
        params["RANGE"] = range

    return _get("ANALYTICS_FIXED_WINDOW", **params)

## Earnings
def earnings_calendar(symbol: str = None, horizon: str = "3month") -> pd.DataFrame:
    if symbol:
        csv_url = f'{BASE_URL}?function=EARNINGS_CALENDAR&symbol={symbol}&horizon={horizon}&apikey={API_KEY}'
    else:
        csv_url = f'{BASE_URL}?function=EARNINGS_CALENDAR&horizon={horizon}&apikey={API_KEY}'
    with requests.Session() as s:
        data = s.get(csv_url)
        decoded_content = data.content.decode('utf-8')
        data = csv.DictReader(decoded_content.splitlines())
        json_array = []
        for row in data:
            json_object = {
                    "symbol": row.get("symbol"),
                    "name": row.get("name"),
                    "reportDate": row.get("reportDate"),
                    "fiscalDateEnding": row.get("fiscalDateEnding"),
                    "estimate": None if row.get("estimate") == "" or row.get("estimate") is None else row.get("estimate"),
                    "currency": row.get("currency")
                }
            json_array.append(json_object)
    return json_array


def earnings_call_transcript(symbol: str, year: int, quarter: int) -> Dict[str, Any]:
    quarter = f"{year}Q{quarter}"
    return _get("EARNINGS_CALL_TRANSCRIPT", symbol=symbol, quarter=quarter)


def company_overview(symbol: str) -> Dict[str, Any]:
    return _get("OVERVIEW", symbol=symbol)

## Fundamentals

def income_statement(symbol: str, period: str = "annual") -> Dict[str, Any]:
    if period not in {"annual", "quarterly"}:
        raise ValueError("period must be 'annual' or 'quarterly'")
    return _get("INCOME_STATEMENT", symbol=symbol, period=period)


def balance_sheet(symbol: str, period: str = "annual") -> Dict[str, Any]:
    if period not in {"annual", "quarterly"}:
        raise ValueError("period must be 'annual' or 'quarterly'")
    return _get("BALANCE_SHEET", symbol=symbol, period=period)


def cash_flow(symbol: str, period: str = "annual") -> Dict[str, Any]:
    if period not in {"annual", "quarterly"}:
        raise ValueError("period must be 'annual' or 'quarterly'")
    return _get("CASH_FLOW", symbol=symbol, period=period)

def earnings(symbol: str) -> Dict[str, Any]:
    return _get("EARNINGS", symbol=symbol)

### Merged Fundamental Data

_IS_FIELDS = ["totalRevenue", "operatingIncome", "ebit", "ebitda", "netIncome", "depreciationAndAmortization"]
_BS_FIELDS = ["totalAssets", "totalLiabilities", "totalShareholderEquity", "cashAndShortTermInvestments", "cashAndCashEquivalentsAtCarryingValue", "longTermDebt", "shortTermDebt", "commonStockSharesOutstanding"]
_CF_FIELDS = ["operatingCashflow", "capitalExpenditures"]
_ER_FIELDS = ["reportedEPS"]

def fundamental_data_from_earning(symbol: str, start_year: int, end_year: int, filings: int = 4) -> Dict[str, Any]:
    """Fetch & merge Alpha Vantage statements into DCF ready dataset."""
    # Fetch raw payloads
    is_payload = income_statement(symbol)
    bs_payload = balance_sheet(symbol)
    cf_payload = cash_flow(symbol)
    er_payload = earnings(symbol)

    # Annual
    annual: Dict[str, Dict[str, Any]] = {}
    for payload, fields in [
        (is_payload.get("annualReports", []), _IS_FIELDS),
        (bs_payload.get("annualReports", []), _BS_FIELDS),
        (cf_payload.get("annualReports", []), _CF_FIELDS),
    ]:
        parsed = _parse_records(payload, fields)
        for d, val in parsed.items():
            annual.setdefault(d, {}).update(val)

    eps_parsed = _parse_records(er_payload.get("annualEarnings", []), _ER_FIELDS)
    for d, val in eps_parsed.items():
        annual.setdefault(d, {}).update(val)

    annual_filtered = {d: v for d, v in annual.items() if start_year <= int(d[:4]) <= end_year}

    annual_out: List[Dict[str, Any]] = []
    for d, metrics in annual_filtered.items():
        metrics["fiscalDateEnding"] = d
        _compute_extras(metrics)
        annual_out.append(metrics)
    annual_out.sort(key=lambda x: x["fiscalDateEnding"], reverse=True)

    # Quarterly
    quarterly: Dict[str, Dict[str, Any]] = {}
    for payload, fields in [
        (is_payload.get("quarterlyReports", []), _IS_FIELDS),
        (bs_payload.get("quarterlyReports", []), _BS_FIELDS),
        (cf_payload.get("quarterlyReports", []), _CF_FIELDS),
    ]:
        parsed = _parse_records(payload, fields)
        for d, val in parsed.items():
            quarterly.setdefault(d, {}).update(val)

    eps_q_parsed = _parse_records(er_payload.get("quarterlyEarnings", []), _ER_FIELDS)
    for d, val in eps_q_parsed.items():
        quarterly.setdefault(d, {}).update(val)

    quarterly_out: List[Dict[str, Any]] = []
    for d, metrics in quarterly.items():
        metrics["fiscalDateEnding"] = d
        _compute_extras(metrics)
        quarterly_out.append(metrics)
    quarterly_out.sort(key=lambda x: x["fiscalDateEnding"], reverse=True)
    quarterly_out = quarterly_out[:filings]

    return {"symbol": symbol.upper(), "annual": annual_out, "quarterly": quarterly_out}

## DCF Valuation
def calculate_dcf(
    symbol: str,
    *,
    start_year: int,
    end_year: int,
    forecast_years: int = 5,
    rf: float = 0.04,
    eq_prem: float = 0.05,
    perp_growth: float = 0.02,
    max_hist_growth: float = 0.20,
) -> Dict[str, Any]:
    """
    Estimate fair value per share with a free-cash-flow DCF.

    Steps
    -----
    1. Pull consolidated statements via `get_fundamental_data_from_earning`.
    2. Derive base-year FCF and a capped historical growth rate.
    3. Project FCFs over `forecast_years` and discount at rf + equity‑premium.
    4. Add a terminal value using the Gordon–Growth model.
    5. Subtract net debt, divide by shares outstanding → intrinsic price.

    Returns
    -------
    dict
        {
          "symbol": "ABC",
          "intrinsicValuePerShare": 123.45,
          "enterpriseValue": 99_999_999,
          "assumptions": { ... },
          "pvCashFlows": [ ... ],   # present-value FCF projections
        }
    """
    # 1 · Pull & sanity‑check data
    data = fundamental_data_from_earning(symbol, start_year, end_year, filings=4)
    annual = data["annual"]
    if not annual:
        raise ValueError("No annual reports available in the specified window.")

    base = annual[0]                          # most‑recent fiscal year (sorted desc)
    fcf0 = base.get("freeCashFlow")
    if fcf0 is None or isnan(fcf0):
        raise ValueError("Missing free cash flow in base year; cannot compute DCF.")

    # 2 · Historical FCF growth (cap extreme values)
    if len(annual) > 1 and annual[1].get("freeCashFlow") not in (None, 0):
        fcf_prev = annual[1]["freeCashFlow"]
        hist_growth = (fcf0 / fcf_prev) - 1.0 if fcf_prev else 0.0
    else:
        hist_growth = 0.05                               # fallback 5 %
    growth_rate = max(-0.10, min(hist_growth, max_hist_growth))

    # 3 · Projection & discounting
    discount_rate = rf + eq_prem                         # assume β ≈ 1
    fcfs: List[float] = []
    pv_fcfs: List[float] = []
    for t in range(1, forecast_years + 1):
        fcf_t = fcf0 * (1 + growth_rate) ** t
        pv_t  = fcf_t / (1 + discount_rate) ** t
        fcfs.append(fcf_t)
        pv_fcfs.append(pv_t)

    # 4 · Terminal value (Gordon Growth)
    terminal_fcf  = fcfs[-1] * (1 + perp_growth)
    terminal_val  = terminal_fcf / (discount_rate - perp_growth)
    pv_terminal   = terminal_val / (1 + discount_rate) ** forecast_years

    # 5 · Enterprise → Equity → Per‑share value
    enterprise_value = sum(pv_fcfs) + pv_terminal
    net_debt  = base.get("netDebt") or 0.0
    equity_value = enterprise_value - net_debt

    shares_out = base.get("commonStockSharesOutstanding")
    intrinsic_ps = equity_value / shares_out if shares_out else None

    return {
        "symbol": symbol.upper(),
        "intrinsicValuePerShare": intrinsic_ps,
        "enterpriseValue": enterprise_value,
        "assumptions": {
            "baseYearFCF": fcf0,
            "growthRate": growth_rate,
            "forecastYears": forecast_years,
            "discountRate": discount_rate,
            "perpetualGrowth": perp_growth,
            "terminalFCF": terminal_fcf,
            "netDebt": net_debt,
            "sharesOutstanding": shares_out,
        },
        "pvCashFlows": pv_fcfs,
        "pvTerminal": pv_terminal,
    }
mcp = FastMCP("AlphaVantage")

@mcp.tool()
def get_dcf_valuation(
    symbol: str,
    start_year: int,
    end_year: int,
    forecast_years: int = 5,
    rf: float = 0.04,
    eq_prem: float = 0.05,
    perp_growth: float = 0.02,
    max_hist_growth: float = 0.20
) -> Dict[str, Any]:
    return calculate_dcf(symbol=symbol, start_year=start_year, end_year=end_year, forecast_years=forecast_years, rf=rf, eq_prem=eq_prem, perp_growth=perp_growth, max_hist_growth=max_hist_growth)

@mcp.tool()
def get_fundamental_data_from_earning(
    symbol: str,
    start_year: int,
    end_year: int,
    filings: int = 4
) -> Dict[str, Any]:
    return fundamental_data_from_earning(symbol=symbol, start_year=start_year, end_year=end_year, filings=filings)

@mcp.tool()
def get_company_overview(symbol: str) -> Dict[str, Any]:
    return company_overview(symbol=symbol)

@mcp.tool()
def get_earnings_calendar(symbol: str = None, horizon: str = "3month") -> pd.DataFrame:
    return earnings_calendar(symbol=symbol, horizon=horizon)

@mcp.tool()
def get_earnings_call_transcript(symbol: str, year: int, quarter: int) -> Dict[str, Any]:
    return earnings_call_transcript(symbol=symbol, year=year, quarter=quarter)

@mcp.tool()
def get_advanced_analytics(
    symbols: Union[str, Sequence[str]],
    interval: str = "DAILY",
    ohlc: str = "close",
    range: str = '6month',
    calculations: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    return advanced_analytics(symbols=symbols, interval=interval, ohlc=ohlc, range=range, calculations=calculations)



__all__: List[str] = [
    "earnings",
    "earnings_calendar",
    "earnings_call_transcript",
    "company_overview",
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "advanced_analytics",
    "get_fundamental_data_from_earning",
]

if __name__ == "__main__":
    mcp.run(transport="stdio")