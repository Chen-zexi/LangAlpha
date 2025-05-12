import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

# Assuming ginzu_interface.py is in the same directory or PYTHONPATH is set up in Docker
from .ginzu_interface import run_ginzu_analysis_for_api, get_initial_analysis_suggestions
# Import necessary items for dropdowns
from .google_sheets import initialize_google_sheets, get_dropdown_options
from .config import SPREADSHEET_ID, INPUT_SHEET_NAME # Assuming these are in your valuation config

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

app = FastAPI(
    title="Valuation Service API",
    description="API for running Ginzu financial analysis",
    version="0.1.0"
)

@app.get("/") # New root endpoint for testing
async def read_root():
    return {"message": "Valuation API is running"}

# --- Pydantic Schemas for this service's API contract ---
# These are based on src/web/schemas.py but defined here for service independence.
# Consider a shared library for schemas in a larger microservices architecture.

class ValuationGinzuRequest(BaseModel):
    ticker: str
    country: str
    us_industry: str
    global_industry: str
    revenue_growth_rate_next_year: Optional[float] = None 
    operating_margin_next_year: Optional[float] = None
    cagr_5yr_revenue: Optional[float] = None
    target_pre_tax_operating_margin: Optional[float] = None
    years_to_converge_margin: Optional[float] = None
    sales_to_capital_ratio_yrs_1_5: Optional[float] = None
    sales_to_capital_ratio_yrs_6_10: Optional[float] = None

class ValuationGinzuResponse(BaseModel):
    message: Optional[str] = None
    estimated_value_per_share: Optional[float] = None
    price: Optional[float] = None
    price_as_percentage_of_value: Optional[float] = None
    error: Optional[str] = None

# --- New Pydantic Model for Initial Analysis Suggestions ---
class InitialAnalysisSuggestionsResponse(BaseModel):
    company_name: Optional[str] = None
    ticker: Optional[str] = None
    
    b26_rev_growth_suggested_pct: Optional[float] = None
    b26_rev_growth_plot_base64: Optional[str] = None
    
    b27_op_margin_suggested_pct: Optional[float] = None
    b27_op_margin_plot_base64: Optional[str] = None
    
    b28_cagr_suggested_pct: Optional[float] = None
    b28_cagr_plot_base64: Optional[str] = None
    
    b29_target_op_margin_suggested_pct: Optional[float] = None
    b29_target_op_margin_plot_base64: Optional[str] = None
    
    b30_years_to_converge_suggested: Optional[float] = None
    # No plot for b30 in HTML
    
    b31_sc_ratio_1_5_suggested: Optional[float] = None
    b32_sc_ratio_6_10_suggested: Optional[float] = None
    b31_sc_ratio_plot_base64: Optional[str] = None # HTML uses one plot for S/C: b31_sc_ratio_plot

    error: Optional[str] = None
    message: Optional[str] = None

# --- API Endpoint ---
@app.post("/run-valuation-analysis", response_model=ValuationGinzuResponse)
async def handle_run_valuation_analysis(request: ValuationGinzuRequest):
    logger.info(f"Valuation service received request for ticker: {request.ticker}")
    try:
        # The run_ginzu_analysis_for_api function expects individual arguments.
        # Pydantic's model_dump() can convert the request model to a dictionary,
        # but the function signature is specific.
        analysis_result_dict = run_ginzu_analysis_for_api(
            company_ticker=request.ticker,
            country=request.country,
            us_industry=request.us_industry,
            global_industry=request.global_industry,
            revenue_growth_rate_next_year=request.revenue_growth_rate_next_year,
            operating_margin_next_year=request.operating_margin_next_year,
            cagr_5yr_revenue=request.cagr_5yr_revenue,
            target_pre_tax_operating_margin=request.target_pre_tax_operating_margin,
            years_to_converge_margin=request.years_to_converge_margin,
            sales_to_capital_ratio_yrs_1_5=request.sales_to_capital_ratio_yrs_1_5,
            sales_to_capital_ratio_yrs_6_10=request.sales_to_capital_ratio_yrs_6_10
        )

        logger.info(f"Valuation for {request.ticker} completed. Result: {analysis_result_dict}")

        if analysis_result_dict.get("error"):
            # Log the error and return it in the response
            logger.error(f"Error during valuation for {request.ticker}: {analysis_result_dict['error']}")
            # We can choose to return a 200 OK with error in body, or an HTTP error code.
            # For now, let's match the GinzuAnalysisResponse schema.
            return ValuationGinzuResponse(**analysis_result_dict)
        
        return ValuationGinzuResponse(**analysis_result_dict)

    except Exception as e:
        logger.error(f"Unexpected error in valuation service for {request.ticker}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred in valuation service: {str(e)}")

# --- New Endpoint for Initial Analysis Suggestions ---
@app.get("/initial-analysis/{ticker}", response_model=InitialAnalysisSuggestionsResponse)
async def handle_get_initial_analysis_suggestions(
    ticker: str,
    country: str,
    us_industry: str,
    global_industry: str
):
    logger.info(f"Valuation service received request for initial analysis suggestions for ticker: {ticker}")
    try:
        suggestions = await get_initial_analysis_suggestions(
            company_ticker=ticker,
            country=country,
            us_industry=us_industry,
            global_industry=global_industry
        )
        if suggestions.get("error"):
            logger.error(f"Error generating initial suggestions for {ticker}: {suggestions['error']}")
            # Return 200 with error in body to match frontend expectations for error display
            return InitialAnalysisSuggestionsResponse(**suggestions)
        
        # Log the presence of plot data for debugging
        plot_keys = [k for k in suggestions.keys() if k.endswith('plot_base64')]
        logger.info(f"Successfully generated initial suggestions for {ticker} with plots: {plot_keys}")
        
        return InitialAnalysisSuggestionsResponse(**suggestions)

    except Exception as e:
        logger.error(f"Unexpected error in valuation service generating initial suggestions for {ticker}: {str(e)}", exc_info=True)
        # This will return a 500 error, which the frontend should also handle
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred while generating initial suggestions: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# --- Endpoints for Dropdown Options ---

async def fetch_dropdown_data(option_type: str, cell_range: str) -> list[str]:
    logger.info(f"Fetching dropdown options for {option_type} from range {cell_range}")
    try:
        # Ensure Google Sheets are initialized. This might be better done at app startup 
        # or per-request if initialization is lightweight and idempotent.
        # For simplicity, calling it here. Consider refactoring for efficiency if it's slow.
        initialize_google_sheets() 
        options = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, cell_range)
        if not options:
            logger.warning(f"No options found for {option_type} ({cell_range}). Returning empty list.")
            return []
        logger.info(f"Successfully fetched {len(options)} options for {option_type}.")
        return options
    except Exception as e:
        logger.error(f"Error fetching dropdown options for {option_type} ({cell_range}): {str(e)}", exc_info=True)
        # Decide how to handle this error. Raising HTTPException will make the endpoint return 500.
        # Alternatively, return an empty list or a specific error structure if the frontend can handle it.
        raise HTTPException(status_code=500, detail=f"Error fetching {option_type} options: {str(e)}")

@app.get("/dropdowns/countries", response_model=List[str])
async def get_countries_dropdown():
    """Endpoint to get country dropdown options."""
    return await fetch_dropdown_data("countries", "B7") # Cell B7 for Country of Incorporation

@app.get("/dropdowns/us-industries", response_model=List[str])
async def get_us_industries_dropdown():
    """Endpoint to get US industry dropdown options."""
    return await fetch_dropdown_data("US industries", "B8") # Cell B8 for US Industry

@app.get("/dropdowns/global-industries", response_model=List[str])
async def get_global_industries_dropdown():
    """Endpoint to get global industry dropdown options."""
    return await fetch_dropdown_data("global industries", "B9") # Cell B9 for Global Industry

# For local development, if you were to run this file directly:
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000) # Port will be managed by Docker Compose 