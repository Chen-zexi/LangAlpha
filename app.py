from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import base64
import io
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for matplotlib
import matplotlib.pyplot as plt
import os
import time

# Import functions from ginzu_interface.py
from src.valuation.ginzu_interface import (
    initialize_google_sheets, 
    get_dropdown_options,
    get_latest_10k_financials,
    forecast_revenue_growth_rate,
    forecast_operating_margin,
    forecast_revenue_cagr,
    forecast_pretarget_operating_margin,
    forecast_sales_to_capital_ratio
)
from src.valuation.config import POLYGON_API_KEY, ALPHA_VANTAGE_API_KEY, SPREADSHEET_ID, INPUT_SHEET_NAME
import src.valuation.google_sheets as gs_manager
from src.valuation.utils import safe_float, retrieve_date

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up static files and templates
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
templates = Jinja2Templates(directory="src/web/templates")

# Initialize Google Sheets connection at startup
@app.on_event("startup")
async def startup_event():
    try:
        # Initialize Google Sheets connection
        initialize_google_sheets()
        print("Google Sheets connection initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize Google Sheets: {str(e)}")

# Pydantic models for requests and responses
class FinalizationInput(BaseModel):
    b26_rev_growth: Optional[float] = None
    b27_op_margin: Optional[float] = None
    b28_cagr: Optional[float] = None
    b29_target_op_margin: Optional[float] = None
    b30_years_to_converge: Optional[float] = None
    b31_sc_ratio_1_5: Optional[float] = None
    b32_sc_ratio_6_10: Optional[float] = None

# Helper function to convert matplotlib plot to base64 encoded image
def plot_to_base64(fig=None):
    if fig is None:
        fig = plt.gcf()  # Get current figure if none is provided
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ginzu", response_class=HTMLResponse)
async def get_ginzu_page(request: Request):
    return templates.TemplateResponse("ginzu.html", {"request": request})

# API Endpoints
@app.get("/api/ginzu/dropdowns/countries")
async def get_countries():
    try:
        countries = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B7')
        return {"status": "success", "options": countries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ginzu/dropdowns/us-industries")
async def get_us_industries():
    try:
        industries = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B8')
        return {"status": "success", "options": industries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ginzu/dropdowns/global-industries")
async def get_global_industries():
    try:
        industries = get_dropdown_options(SPREADSHEET_ID, INPUT_SHEET_NAME, 'B9')
        return {"status": "success", "options": industries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/{ticker}/initial")
async def get_initial_analysis(ticker: str, country: str, us_industry: str, global_industry: str):
    try:
        # Validate API keys
        if not POLYGON_API_KEY or not ALPHA_VANTAGE_API_KEY:
            raise HTTPException(status_code=500, detail="API keys for Polygon or Alpha Vantage are missing")

        # Get latest financials
        financials = get_latest_10k_financials(ticker, ALPHA_VANTAGE_API_KEY)
        if "error" in financials:
            raise HTTPException(status_code=404, detail=f"Could not fetch financials for {ticker}: {financials['error']}")
        
        # Update sheet with initial values
        date_val = retrieve_date()
        gs_manager.input_worksheet.update_acell('B3', date_val)
        gs_manager.input_worksheet.update_acell('B4', financials.get("B4", ticker))
        gs_manager.input_worksheet.update_acell('B7', country)
        gs_manager.input_worksheet.update_acell('B8', us_industry)
        gs_manager.input_worksheet.update_acell('B9', global_industry)
        
        # Generate forecasts and plots
        response_data = {
            "ticker": ticker,
            "company_name": financials.get("B4", ticker)
        }
        
        # Revenue Growth Rate forecast
        try:
            rev_growth_forecast = forecast_revenue_growth_rate(ticker, ALPHA_VANTAGE_API_KEY, plot=True)
            if not rev_growth_forecast.get("error", False):
                response_data["b26_rev_growth_suggested_pct"] = rev_growth_forecast.get('growth_rate', 0) * 100
                # For plot, we capture the current figure after the forecast function has plotted it
                response_data["b26_rev_growth_plot_base64"] = plot_to_base64()
        except Exception as e:
            print(f"Error generating revenue growth forecast: {e}")
            response_data["b26_rev_growth_suggested_pct"] = None
        
        # Operating Margin forecast
        try:
            op_margin_forecast = forecast_operating_margin(ticker, ALPHA_VANTAGE_API_KEY, plot=True)
            if not op_margin_forecast.get("error", False):
                response_data["b27_op_margin_suggested_pct"] = op_margin_forecast.get('margin_forecast', 0)
                response_data["b27_op_margin_plot_base64"] = plot_to_base64()
        except Exception as e:
            print(f"Error generating operating margin forecast: {e}")
            response_data["b27_op_margin_suggested_pct"] = None
        
        # Revenue CAGR forecast
        try:
            cagr_forecast = forecast_revenue_cagr(ticker, ALPHA_VANTAGE_API_KEY, forecast_years=5, growth='logistic', plot=True)
            if not cagr_forecast.get("error", False):
                response_data["b28_cagr_suggested_pct"] = cagr_forecast.get('cagr_forecast', 0) * 100
                response_data["b28_cagr_plot_base64"] = plot_to_base64()
        except Exception as e:
            print(f"Error generating CAGR forecast: {e}")
            response_data["b28_cagr_suggested_pct"] = None
        
        # Pre-target Operating Margin forecast
        try:
            pre_target_margin_forecast = forecast_pretarget_operating_margin(ticker, ALPHA_VANTAGE_API_KEY, plot=True)
            if not pre_target_margin_forecast.get("error", False):
                response_data["b29_target_op_margin_suggested_pct"] = pre_target_margin_forecast.get('target_margin', 0)
                response_data["b30_years_to_converge_suggested"] = pre_target_margin_forecast.get('years_to_converge', 5)
                response_data["b29_target_op_margin_plot_base64"] = plot_to_base64()
        except Exception as e:
            print(f"Error generating target operating margin forecast: {e}")
            response_data["b29_target_op_margin_suggested_pct"] = None
            response_data["b30_years_to_converge_suggested"] = None
        
        # Sales to Capital Ratio forecast
        try:
            sc_ratio_forecast = forecast_sales_to_capital_ratio(ticker, ALPHA_VANTAGE_API_KEY, plot=True)
            if not sc_ratio_forecast.get("error", False):
                response_data["b31_sc_ratio_1_5_suggested"] = sc_ratio_forecast.get('avg_1_5', 0)
                response_data["b32_sc_ratio_6_10_suggested"] = sc_ratio_forecast.get('avg_6_10', 0)
                response_data["b31_sc_ratio_plot_base64"] = plot_to_base64()
        except Exception as e:
            print(f"Error generating sales to capital ratio forecast: {e}")
            response_data["b31_sc_ratio_1_5_suggested"] = None
            response_data["b32_sc_ratio_6_10_suggested"] = None
        
        return {"status": "success", "data": response_data}
    
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analysis/{ticker}/finalize")
async def finalize_analysis(ticker: str, input_data: FinalizationInput):
    try:
        # Update the sheet with the user's chosen values
        updates = {}
        if input_data.b26_rev_growth is not None:
            updates['B26'] = input_data.b26_rev_growth
        
        if input_data.b27_op_margin is not None:
            updates['B27'] = input_data.b27_op_margin
            
        if input_data.b28_cagr is not None:
            updates['B28'] = input_data.b28_cagr
            
        if input_data.b29_target_op_margin is not None:
            updates['B29'] = input_data.b29_target_op_margin
            
        if input_data.b30_years_to_converge is not None:
            updates['B30'] = input_data.b30_years_to_converge
            
        if input_data.b31_sc_ratio_1_5 is not None:
            updates['B31'] = input_data.b31_sc_ratio_1_5
            
        if input_data.b32_sc_ratio_6_10 is not None:
            updates['B32'] = input_data.b32_sc_ratio_6_10
        
        # Update the spreadsheet
        print("Updating sheet with value drivers:")
        for cell, value in updates.items():
            try:
                gs_manager.input_worksheet.update_acell(cell, value)
                print(f"Updated {cell}: {value}")
            except Exception as e:
                print(f"Error updating cell {cell} with value {value}: {e}")
                raise HTTPException(status_code=500, detail=f"Error updating cell {cell}: {str(e)}")
        
        # Pause for sheet calculations
        print("Pausing for sheet calculations...")
        time.sleep(7)
        
        # Get final valuation metrics
        try:
            if not gs_manager.valuation_worksheet:
                raise HTTPException(status_code=500, detail="Valuation worksheet not initialized")
                
            val_b33_str = gs_manager.valuation_worksheet.acell('B33').value
            val_b34_str = gs_manager.valuation_worksheet.acell('B34').value
            val_b35_str = gs_manager.valuation_worksheet.acell('B35').value
            
            est_value_num = safe_float(val_b33_str)
            price_num = safe_float(val_b34_str)
            perc_val_num = safe_float(val_b35_str)
            
            # Prepare response data
            response_data = {
                "estimated_value_per_share": est_value_num,
                "price": price_num,
                "price_as_percent_of_value": perc_val_num
            }
            
            return {"status": "success", "data": response_data}
        
        except Exception as e:
            print(f"Error reading final valuation metrics: {e}")
            raise HTTPException(status_code=500, detail=f"Error reading valuation metrics: {str(e)}")
    
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) 