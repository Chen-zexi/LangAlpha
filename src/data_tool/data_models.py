## This file is copied from the repo https://github.com/virattt/ai-hedge-fund
## Original author: Virat Singh https://github.com/virattt
## Modified by Zexi Chen https://github.com/Chen-zexi

from pydantic import BaseModel


class Price(BaseModel):
    open: float
    close: float
    high: float
    low: float
    volume: int
    time: str


class PriceResponse(BaseModel):
    ticker: str
    prices: list[Price]


class FinancialMetrics(BaseModel):
    ticker: str
    report_period: str
    period: str
    currency: str | None = None
    
    # Valuation & Comparison
    market_cap: float | None = None
    earnings_growth: float | None = None
    fcf_yield: float | None = None
    
    # Profitability
    return_on_equity: float | None = None
    return_on_invested_capital: float | None = None
    operating_margin: float | None = None
    gross_margin: float | None = None
    earnings_per_share: float | None = None
    basic_eps: float | None = None
    diluted_eps: float | None = None
    net_income: float | None = None
    revenue: float | None = None
    
    # Financial Health & Risk
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    
    # Share Structure & Dividends
    book_value_per_share: float | None = None
    outstanding_shares: float | None = None
    dividends: float | None = None
    special_distributions: float | None = None
    
    # Other
    free_cash_flow: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None


class FinancialMetricsResponse(BaseModel):
    financial_metrics: list[FinancialMetrics]


class LineItem(BaseModel):
    ticker: str
    report_period: str
    period: str
    currency: str

    # Allow additional fields dynamically
    model_config = {"extra": "allow"}


class LineItemResponse(BaseModel):
    search_results: list[LineItem]


class InsiderTrade(BaseModel):
    ticker: str
    issuer: str | None
    name: str | None
    title: str | None
    is_board_director: bool | None
    transaction_date: str | None
    transaction_shares: float | None
    transaction_price_per_share: float | None
    transaction_value: float | None
    shares_owned_before_transaction: float | None
    shares_owned_after_transaction: float | None
    security_title: str | None
    filing_date: str


class InsiderTradeResponse(BaseModel):
    insider_trades: list[InsiderTrade]


# polygon news

class insights(BaseModel):
    ticker: str
    sentiment: str
    sentiment_reasoning: str
    
    model_config = {
        "extra": "ignore",
    }
    
    
class company_news(BaseModel):
    article_url: str
    author: str
    description: str
    id: str
    insights: list[insights]
    keywords: list[str]
    published_utc: str
    tickers: list[str]
    title: str
    publisher: str  
    
    model_config = {
        "extra": "ignore",
        "arbitrary_types_allowed": True,
    }
    
class company_news_response(BaseModel):
    count: int
    results: list[company_news]
    
    model_config = {
        "extra": "ignore",
        "arbitrary_types_allowed": True,
    }


class RetailActivity(BaseModel):
    ticker: str
    date: str
    activity: float
    sentiment: int
    
class RetailActivityResponse(BaseModel):
    results: list[RetailActivity]


class Position(BaseModel):
    cash: float = 0.0
    shares: int = 0
    ticker: str


class Portfolio(BaseModel):
    positions: dict[str, Position]  # ticker -> Position mapping
    total_cash: float = 0.0


class AnalystSignal(BaseModel):
    signal: str | None = None
    confidence: float | None = None
    reasoning: dict | str | None = None
    max_position_size: float | None = None  # For risk management signals


class TickerAnalysis(BaseModel):
    ticker: str
    analyst_signals: dict[str, AnalystSignal]  # agent_name -> signal mapping


class AgentStateData(BaseModel):
    tickers: list[str]
    portfolio: Portfolio
    start_date: str
    end_date: str
    ticker_analyses: dict[str, TickerAnalysis]  # ticker -> analysis mapping


class AgentStateMetadata(BaseModel):
    show_reasoning: bool = False
    model_config = {"extra": "allow"}
