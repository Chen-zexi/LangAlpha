import asyncio
import os # For environment variables
import httpx # For making HTTP requests to the valuation service
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Any, Dict, List
import logging # For logging

# Import schemas
from ..schemas import GinzuAnalysisRequest, GinzuAnalysisResponse

# --- New Pydantic Model for Initial Analysis Suggestions (mirroring valuation service) ---
# Consider moving to schemas.py if used elsewhere in web service
from pydantic import BaseModel # Ensure pydantic.BaseModel is imported
from typing import Optional # Ensure Optional is imported

class WebInitialAnalysisSuggestionsResponse(BaseModel):
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
    b31_sc_ratio_1_5_suggested: Optional[float] = None
    b32_sc_ratio_6_10_suggested: Optional[float] = None
    b31_sc_ratio_plot_base64: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None

# Import the refactored Ginzu logic
# The path might need adjustment based on how Python resolves modules from src/web/routers/
# Assuming standard Python path behavior where 'src' is a top-level package or on PYTHONPATH

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ginzu",
    tags=["ginzu"],
)

# Get the Valuation API URL from environment variable, with a default for local Docker Compose
VALUATION_API_BASE_URL = os.getenv("VALUATION_API_URL", "http://valuation-api:8000")

# In-memory store for task results (simple approach, consider a more robust solution for production)
# This is just to store the final result. The actual processing happens in the background.
results_store: Dict[str, Any] = {} 

async def background_ginzu_analysis_wrapper(task_id: str, request_data: GinzuAnalysisRequest):
    """
    Wrapper to run the Ginzu analysis in the background and store its result.
    """
    try:
        # This is where the refactored ginzu_interface.py function will be called.
        # For now, let's simulate some work and a result.
        # results = await run_ginzu_analysis_for_api(request_data) # This will be the actual call
        
        await asyncio.sleep(5) # Simulate work
        simulated_results = {
            "message": f"Analysis for {request_data.ticker} completed.",
            "estimated_value_per_share": 150.75,
            "price": 140.50,
            "price_as_percentage_of_value": (140.50 / 150.75) * 100,
            "error": None
        }
        results_store[task_id] = GinzuAnalysisResponse(**simulated_results)

    except Exception as e:
        results_store[task_id] = GinzuAnalysisResponse(error=f"An unexpected error occurred: {str(e)}")


@router.post("/run-analysis", response_model=GinzuAnalysisResponse)
async def run_analysis(request: GinzuAnalysisRequest):
    """
    Endpoint to trigger Ginzu financial analysis by calling the valuation-api service.
    """
    logger.info(f"Web-API received Ginzu analysis request for ticker: {request.ticker}, forwarding to valuation-api.")
    
    valuation_request_payload = request.model_dump()
    # The new valuation service endpoint is /run-valuation-analysis
    target_url = f"{VALUATION_API_BASE_URL}/run-valuation-analysis"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client: # Increased timeout for potentially long analysis
            response = await client.post(target_url, json=valuation_request_payload)
            response.raise_for_status() # Raise an exception for 4XX/5XX responses
            
            # Assuming the valuation service responds with a JSON compatible with GinzuAnalysisResponse
            # (or its own ValuationGinzuResponse which should be structurally similar)
            response_data = response.json()
            logger.info(f"Received response from valuation-api for {request.ticker}: {response_data}")
            
            # Check if the response_data from valuation-api contains an error key, as per its own logic
            if response_data.get("error"):
                # Forward the error. You might want to map status codes or messages here.
                # For simplicity, we create a GinzuAnalysisResponse with the error.
                return GinzuAnalysisResponse(
                    message=response_data.get("message"), # It might still have a message
                    error=response_data.get("error"),
                    # Ensure all required fields have default values to avoid validation errors
                    estimated_value_per_share=None,
                    price=None,
                    price_as_percentage_of_value=None
                )

            # Ensure all required fields are present
            result_data = {
                "message": response_data.get("message"),
                "estimated_value_per_share": response_data.get("estimated_value_per_share"),
                "price": response_data.get("price"),
                "price_as_percentage_of_value": response_data.get("price_as_percentage_of_value"),
                "error": response_data.get("error")
            }
            return GinzuAnalysisResponse(**result_data)

    except httpx.HTTPStatusError as e:
        # Error from the valuation service (e.g., 4xx, 5xx)
        error_detail = f"Error from valuation service: {e.response.status_code}. "
        try:
            error_detail += e.response.json().get("detail", str(e.response.text))
        except Exception:
            error_detail += str(e.response.text)
        logger.error(f"HTTPStatusError calling valuation-api for {request.ticker}: {error_detail}")
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        # Network error or other issue connecting to the valuation service
        logger.error(f"RequestError calling valuation-api for {request.ticker}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Could not connect to valuation service: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in web-api while calling valuation-api for {request.ticker}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {str(e)}")

# Example of how one might fetch results if using background tasks with a results store:
# @router.get("/results/{task_id}", response_model=GinzuAnalysisResponse)
# async def get_analysis_result(task_id: str):
#     result = results_store.get(task_id)
#     if result is None:
#         raise HTTPException(status_code=404, detail="Task not found or not yet completed.")
#     return result 

# --- Proxy Endpoints for Dropdown Options ---
async def fetch_dropdown_from_valuation_api(dropdown_type: str, valuation_api_path: str) -> List[str]:
    target_url = f"{VALUATION_API_BASE_URL}{valuation_api_path}"
    logger.info(f"Web-API fetching {dropdown_type} from valuation-api: {target_url}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(target_url)
            response.raise_for_status() # Raise an exception for 4XX/5XX responses
            data = response.json()
            if not isinstance(data, list):
                logger.error(f"Valuation API did not return a list for {dropdown_type}. Got: {type(data)}")
                raise HTTPException(status_code=500, detail=f"Invalid data format from valuation service for {dropdown_type}.")
            logger.info(f"Web-API successfully fetched {len(data)} {dropdown_type} from valuation-api.")
            return data
    except httpx.HTTPStatusError as e:
        error_detail = f"Error from valuation service fetching {dropdown_type}: {e.response.status_code}. "
        try:
            error_detail += e.response.json().get("detail", str(e.response.text))
        except Exception:
            error_detail += str(e.response.text)
        logger.error(f"HTTPStatusError from valuation-api for {dropdown_type}: {error_detail}")
        # Forward the status code from the downstream service if it's a 4xx or 5xx error
        raise HTTPException(status_code=e.response.status_code, detail=error_detail)
    except httpx.RequestError as e:
        logger.error(f"RequestError calling valuation-api for {dropdown_type}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Could not connect to valuation service for {dropdown_type}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in web-api while fetching {dropdown_type} from valuation-api: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred while fetching {dropdown_type}.")

@router.get("/dropdowns/countries", response_model=List[str])
async def get_countries():
    return await fetch_dropdown_from_valuation_api("countries", "/dropdowns/countries")

@router.get("/dropdowns/us-industries", response_model=List[str])
async def get_us_industries():
    return await fetch_dropdown_from_valuation_api("US industries", "/dropdowns/us-industries")

@router.get("/dropdowns/global-industries", response_model=List[str])
async def get_global_industries():
    return await fetch_dropdown_from_valuation_api("global industries", "/dropdowns/global-industries")

# --- New GET Endpoint for Initial Analysis Suggestions ---
@router.get("/analysis/{ticker}/initial", response_model=WebInitialAnalysisSuggestionsResponse)
async def get_initial_analysis(
    ticker: str,
    country: str, # These will be query parameters from the frontend
    us_industry: str,
    global_industry: str
):
    logger.info(f"Web-API received request for initial Ginzu analysis for ticker: {ticker}")
    target_url = f"{VALUATION_API_BASE_URL}/initial-analysis/{ticker}"
    
    query_params = {
        "country": country,
        "us_industry": us_industry,
        "global_industry": global_industry
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client: # Timeout for fetching suggestions
            response = await client.get(target_url, params=query_params)
            response.raise_for_status() # Raise an exception for 4XX/5XX responses
            
            response_data = response.json()
            logger.info(f"Received initial analysis suggestions from valuation-api for {ticker}: {response_data}")
            
            # Check for error in the response from valuation-api
            if response_data.get("error"):
                # Pass through the error details
                return WebInitialAnalysisSuggestionsResponse(**response_data)

            return WebInitialAnalysisSuggestionsResponse(**response_data)

    except httpx.HTTPStatusError as e:
        error_detail = f"Error from valuation service (initial analysis): {e.response.status_code}. "
        try:
            error_detail += e.response.json().get("detail", str(e.response.text))
        except Exception:
            error_detail += str(e.response.text)
        logger.error(f"HTTPStatusError calling valuation-api for initial analysis of {ticker}: {error_detail}")
        # Return a response compatible with WebInitialAnalysisSuggestionsResponse, including the error
        return WebInitialAnalysisSuggestionsResponse(error=error_detail, message="Failed to fetch initial analysis suggestions.")
    except httpx.RequestError as e:
        logger.error(f"RequestError calling valuation-api for initial analysis of {ticker}: {str(e)}")
        return WebInitialAnalysisSuggestionsResponse(error=f"Could not connect to valuation service for initial analysis: {str(e)}", message="Network error fetching suggestions.")
    except Exception as e:
        logger.error(f"Unexpected error in web-api while fetching initial analysis for {ticker}: {str(e)}", exc_info=True)
        return WebInitialAnalysisSuggestionsResponse(error=f"An unexpected server error occurred: {str(e)}", message="Server error fetching suggestions.") 