from __future__ import annotations
from typing import Dict, Any, List
import pandas as pd
from yahooquery import Ticker
from mcp.server.fastmcp import FastMCP
from langgraph.config import get_stream_writer

# ────────────────────────── INTERNAL ────────────────────────── #

def _tkr(ticker: str, **kwargs) -> Ticker:
    return Ticker(ticker, **kwargs)


def _safe_get(d: Dict[str, Any], *path, default=None):
    """Safely retrieve nested dictionary values with debug info if missing."""
    current = d
    full_path = '.'.join(str(p) for p in path)
    
    for key in path:
        current = current.get(key, {})
        
    return current



# ───────────── 2) CATALYST CALENDAR & CONSENSUS ───────────── #

def event_expectations(ticker: str, **kw) -> Dict[str, Any]:
    tk = _tkr(ticker, **kw)
    ce = tk.calendar_events.get(ticker, {})
    et = tk.earnings_trend.get(ticker, {})
    
    
    eps_nodes = {n["period"]: n for n in et.get("trend", [])} if et else {}
    
    consensus = {
        "epsNxtQ": _safe_get(eps_nodes, "0q", "earningsEstimate"),
        "revNxtQ": _safe_get(eps_nodes, "0q", "revenueEstimate"),
        "epsNxtY": _safe_get(eps_nodes, "+1y", "earningsEstimate"),
        "revNxtY": _safe_get(eps_nodes, "+1y", "revenueEstimate")
    }
    
    return {
        "ticker": ticker,
        "nextEarnings": _safe_get(ce, "earnings", "earningsDate", default=[None])[0],
        "exDiv": ce.get("exDividendDate"),
        "consensus": consensus
    }


# ───────────── 3) FUNDAMENTALS (VALUE & QUALITY) ──────────── #

def fundamental_summary(ticker: str, **kw) -> Dict[str, Any]:
    tk = _tkr(ticker, **kw)
    fd = tk.financial_data.get(ticker, {})
    ks = tk.key_stats.get(ticker, {})
    summary = tk.summary_detail.get(ticker, {})
    
    
    ev = ks.get("enterpriseValue")
    ebitda = fd.get("ebitda") or ks.get("ebitda")
    
    
    ev_ebitda = None
    if ev and ebitda and ebitda != 0:
        ev_ebitda = ev / ebitda
    
    return {
        "ticker": ticker,
        "valuation": {
            "MarketCap": summary.get("marketCap"),
            "PE": summary.get("trailingPE"),
            "fwdPE": summary.get("forwardPE"),
            "EV_Ebitda": ev_ebitda,
            "fiftyTwoWeekLow": summary.get("fiftyTwoWeekLow"),
            "fiftyTwoWeekHigh": summary.get("fiftyTwoWeekHigh"),
        },
        "margins": {
            "gross": fd.get("grossMargins"), 
            "oper": fd.get("operatingMargins"),
            "net": fd.get("profitMargins")
        },
        "growth": {
            "rev": fd.get("revenueGrowth"), 
            "eps": fd.get("earningsGrowth")
        },
        "liquidity": {
            "netDebt": (fd.get("totalDebt") or 0) - (fd.get("cash") or 0),
            "currentRatio": fd.get("currentRatio")
        },
    }


# ─────────────── 4) OWNERSHIP & ANALYST FLOW ─────────────── #

def ownership_sentiment(ticker: str, n=5, **kw) -> Dict[str, Any]:
    tk = _tkr(ticker, **kw)
    mh = tk.major_holders.get(ticker, {})
    rt = tk.recommendation_trend
    
    rating = rt.xs(ticker, level=0).iloc[0].to_dict()

    # Get grading history more safely
    gh = tk.grading_history
    acts = []


    required_cols = ["firm", "toGrade", "fromGrade", "action", "epochGradeDate"]

    acts = gh.sort_values("epochGradeDate", ascending=False).head(n)[required_cols].to_dict("records")

    
    return {
        "ticker": ticker,
        "holders": {k: mh.get(k) for k in ("insidersPercentHeld", "institutionsPercentHeld")},
        "analystSplit": rating,
        "recentActions": acts
    }


# ───────────── 5) DISCOUNTED-CASH-FLOW SNAPSHOT ───────────── #

def dcf_valuation(ticker: str,
                  rf=0.04, eq_prem=0.05, perp_g=0.02, cap_g=0.20, **kw) -> Dict[str, Any]:
    tk = _tkr(ticker, **kw)
    
    # Get financial data and key stats for baseline calculations
    fd = tk.financial_data.get(ticker, {})
    ks = tk.key_stats.get(ticker, {})
    summary = tk.summary_detail.get(ticker, {})
    
    
    # Find price data from any available source
    price = summary.get("previousClose")
    
    beta = summary.get("beta") or 1.0
    
    # Calculate discount rate from beta
    disc = rf + beta * eq_prem
    
    # Try simplified earnings-based valuation
    try:
        # Get key metrics
        earnings_ttm = ks.get("trailingEps")
            
        growth_rate = fd.get("earningsGrowth")

        future_pe = summary.get("forwardPE")
            
        shares = ks.get("sharesOutstanding")
            
        if earnings_ttm and growth_rate and shares:
            # Simple 5-year DCF based on earnings growth
            g = max(-cap_g, min(cap_g, growth_rate))  # Cap growth rate
            future_eps = earnings_ttm * (1 + g) ** 5  # 5-year future EPS
            future_price = future_eps * future_pe  # Terminal value based on PE
            pv_future_price = future_price / ((1 + disc) ** 5)  # Discount to present
            
            # Add NPV of dividends if available
            dividend_yield = summary.get("dividendYield") or 0
            dividends_pv = 0
            if dividend_yield > 0:
                div_per_share = price * dividend_yield
                for i in range(1, 6):
                    dividends_pv += (div_per_share * (1 + g/2) ** (i-1)) / ((1 + disc) ** i)
                    
            intrinsic = pv_future_price + dividends_pv
            
            return {
                "ticker": ticker,
                "intrinsicPS": round(intrinsic, 2),
                "price": price,
                "upsidePct": round((intrinsic / price - 1) * 100, 1),
                "inputs": {"g": round(g, 3), "disc": round(disc, 3), "method": "earnings-based"}
            }
    except Exception as e:
        print(f"DEBUG: Error in earnings-based DCF: {e}")




# ──────────── 9) ONE-CALL DASHBOARD ──────────── #

def comprehensive_dashboard(ticker: str, **kw) -> Dict[str, Any]:
    return {
        "events": event_expectations(ticker, **kw),
        "fundamentals": fundamental_summary(ticker, **kw),
        "ownership": ownership_sentiment(ticker, **kw),
        "DCF": dcf_valuation(ticker, **kw)
    }


# ───────────── MCP SERVER SETUP ───────────── #

# Initialize FastMCP server
mcp = FastMCP("YahooQuery")

@mcp.tool()
def get_event_expectations(ticker: str) -> Dict[str, Any]:
    """
    Get information about upcoming events and analyst expectations.
    
    Args:
        ticker: The ticker symbol.
        
    Returns:
        A dictionary containing information about upcoming earnings dates,
        ex-dividend dates, and analyst consensus estimates.
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving event expectations for {ticker}")
    return event_expectations(ticker)

@mcp.tool()
def get_fundamental_summary(ticker: str) -> Dict[str, Any]:
    """
    Get fundamental financial metrics for value and quality analysis.
    
    Args:
        ticker: The ticker symbol.
        
    Returns:
        A dictionary containing valuation metrics (P/E, EV/EBITDA), margin data,
        growth rates, and liquidity ratios.
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving fundamental data for {ticker}")
    return fundamental_summary(ticker)

@mcp.tool()
def get_ownership_sentiment(ticker: str, n: int = 5) -> Dict[str, Any]:
    """
    Get information about stock ownership and analyst sentiment.
    
    Args:
        ticker: The ticker symbol.
        n: Number of top funds and recent analyst actions to include (default: 5).
        
    Returns:
        A dictionary containing insider/institutional ownership percentages,
        analyst recommendations, and recent rating changes.
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving analyst consensus for {ticker}")
    return ownership_sentiment(ticker, n)

@mcp.tool()
def get_dcf_valuation(
    ticker: str,
    rf: float = 0.04, 
    eq_prem: float = 0.05, 
    perp_g: float = 0.02, 
    cap_g: float = 0.20
) -> Dict[str, Any]:
    """
    Get a simplified discounted cash flow valuation for a stock.
    
    Args:
        ticker: The ticker symbol.
        rf: Risk-free rate (default: 0.04).
        eq_prem: Equity risk premium (default: 0.05).
        perp_g: Perpetual growth rate (default: 0.02).
        cap_g: Growth rate cap (default: 0.20).
        
    Returns:
        A dictionary containing intrinsic price per share, current price,
        potential upside percentage, and the inputs used for calculation.
    """
    writer = get_stream_writer()
    writer.write(f"Calculating intrinsic value for {ticker}")
    return dcf_valuation(ticker, rf, eq_prem, perp_g, cap_g)



@mcp.tool()
def get_comprehensive_dashboard(ticker: str) -> Dict[str, Any]:
    """
    Get a comprehensive dashboard for a stock that includes events, analyst ratings,fundamentals, ownership, and DCF.
    
    Args:
        ticker: The ticker symbol.
        
    Returns:
        A dictionary containing results from all available analysis methods combined:
        events, fundamentals, ownership, DCF.
    """
    writer = get_stream_writer()
    writer.write(f"Retrieving comprehensive fundamental data for {ticker}")
    return comprehensive_dashboard(ticker)


# ───────── QUICK SMOKE-TEST ───────── #
if __name__ == "__main__":
    mcp.run(transport="stdio")