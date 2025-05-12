import pandas as pd
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression
import requests
import io
import base64

from .utils import safe_float
from .data_providers import get_alpha_vantage_data # Assuming API key is passed if needed, or handled by get_alpha_vantage_data

def plot_to_base64(fig):
    """Convert a matplotlib figure to a base64 encoded string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"

def get_annual_financial_data(symbol, api_key, data_type="revenue", history_years=15):
    """Fetches and prepares annual financial data for Prophet."""
    url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={api_key}"
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        print(f"Request failed for {symbol} income statement (status {response.status_code}).")
        return pd.DataFrame()
    
    data = response.json()
    if "annualReports" not in data or not data["annualReports"]:
        api_message = data.get('Information', data.get('Note', 'No further info from API.'))
        print(f"No annualReports found for symbol {symbol}. API Message: {api_message}")
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
            print(f"Skipping report for {symbol} (date: {report.get('fiscalDateEnding')}) due to error processing {data_type}: {e}")
    
    df = pd.DataFrame(records).sort_values("ds").reset_index(drop=True)
    
    if not df.empty:
        cutoff_date = pd.Timestamp.today() - pd.DateOffset(years=history_years)
        df = df[df['ds'] >= cutoff_date]
    
    return df

def forecast_revenue_growth_rate(symbol, api_key, history_years=5, cps_grid=None, plot=True):
    """Forecasts revenue growth rate."""
    print(f"\nForecasting Revenue Growth Rate for {symbol}...")
    if cps_grid is None: cps_grid = [0.01, 0.05, 0.1, 0.2, 0.3]
    df_revenue = get_annual_financial_data(symbol, api_key, "revenue", history_years)
    
    plot_data = None
    
    if len(df_revenue) < 4: # For CV
        print(f"Not enough revenue data for Prophet CV for {symbol} (need at least 4, got {len(df_revenue)}).")
        if len(df_revenue) >=2: 
            model = Prophet(yearly_seasonality=False, changepoint_prior_scale=0.05).fit(df_revenue)
            future = model.make_future_dataframe(periods=1, freq='A')
            forecast = model.predict(future)
            last_actual = df_revenue.iloc[-1]["y"]; next_forecast = forecast.iloc[-1]["yhat"]
            growth_rate = (next_forecast - last_actual) / last_actual if last_actual != 0 else 0.0
            if plot: 
                try: 
                    fig = model.plot(forecast)
                    plt.title(f"Revenue Forecast (Simple) for {symbol}")
                    plot_data = plot_to_base64(fig)
                except Exception as e: print(f"Plotting error: {e}")
            return {"growth_rate": growth_rate, "best_cps": 0.05, "error": "Insufficient data for CV, simple forecast used.", "plot_base64": plot_data}
        return {"growth_rate": 0.0, "error": "Insufficient data for any forecast", "plot_base64": plot_data}

    tuning = []; best_cps = 0.05
    n_years_data = len(df_revenue)
    initial_cv_years = min(max(2, n_years_data - 2), n_years_data -1) 
    
    if n_years_data >= initial_cv_years + 2: # initial + period (1) + horizon (1)
        for cps_val in cps_grid:
            m = Prophet(yearly_seasonality=False, changepoint_prior_scale=cps_val, n_changepoints=min(5, len(df_revenue)-1))
            m.fit(df_revenue)
            try:
                df_cv = cross_validation(m, initial=f"{int(initial_cv_years * 365.25)} days", period="365 days", horizon="365 days", parallel=None)
                perf = performance_metrics(df_cv)
                tuning.append({"cps": cps_val, "mape": perf['mape'].mean()})
            except Exception as e: print(f"Prophet CV (Rev Growth) for {symbol}, cps={cps_val}, failed: {e}")
        if tuning: best_cps = min(tuning, key=lambda x: x["mape"])["cps"]
    else: print(f"Skipping Prophet CV for {symbol} (Rev Growth) due to limited data ({n_years_data}). Using default CPS.")

    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(5, len(df_revenue)-1))
    model.fit(df_revenue)
    future = model.make_future_dataframe(periods=1, freq='A'); forecast = model.predict(future)
    last_actual_revenue = df_revenue.iloc[-1]["y"]; next_forecast_revenue = forecast.iloc[-1]["yhat"]
    growth_rate = (next_forecast_revenue - last_actual_revenue) / last_actual_revenue if last_actual_revenue != 0 else 0.0
    
    if plot:
        try: 
            fig = model.plot(forecast)
            plt.title(f"Forecasted Revenue for {symbol} (Best CPS: {best_cps:.2f})")
            plt.xlabel("Date")
            plt.ylabel("Revenue")
            plt.tight_layout()
            plot_data = plot_to_base64(fig)
        except Exception as e: print(f"Error plotting revenue forecast for {symbol}: {e}")

    print(f"Revenue Growth Forecast for {symbol}: {growth_rate*100:.2f}% (CPS: {best_cps})")
    return {"growth_rate": growth_rate, "last_actual_revenue": last_actual_revenue, "forecasted_next_year_revenue": next_forecast_revenue, "best_cps": best_cps, "plot_base64": plot_data}

def forecast_operating_margin(symbol, api_key, history_years=10, cps_grid=None, plot=True):
    """Forecasts operating margin."""
    print(f"\nForecasting Operating Margin for {symbol}...")
    if cps_grid is None: cps_grid = [0.01, 0.05, 0.1, 0.3, 0.5]
    df_margin = get_annual_financial_data(symbol, api_key, "operating_margin", history_years)

    plot_data = None

    if len(df_margin) < 4:
        print(f"Not enough op margin data for Prophet CV for {symbol} (need at least 4, got {len(df_margin)}).")
        if len(df_margin) >=2:
            model = Prophet(yearly_seasonality=False, changepoint_prior_scale=0.05).fit(df_margin)
            future = model.make_future_dataframe(periods=1, freq='A'); forecast = model.predict(future)
            if plot: 
                try: 
                    fig = model.plot(forecast)
                    plt.title(f"Op Margin Forecast (Simple) for {symbol}")
                    plot_data = plot_to_base64(fig)
                except Exception as e: print(f"Plotting error: {e}")
            return {"margin_forecast": forecast.iloc[-1]['yhat'], "best_cps": 0.05, "error": "Insufficient data for CV, simple forecast used.", "plot_base64": plot_data}
        return {"margin_forecast": 0.0, "error": "Insufficient data for any forecast", "plot_base64": plot_data}

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
            except Exception as e: print(f"Prophet CV (Op Margin) for {symbol}, cps={cps_val}, failed: {e}")
        if tuning: best_cps = min(tuning, key=lambda x: x['mape'])['cps']
    else: print(f"Skipping Prophet CV for {symbol} (Op Margin) due to limited data ({n_years_data}). Using default CPS.")

    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=best_cps, n_changepoints=min(5, len(df_margin)-1))
    model.fit(df_margin)
    future = model.make_future_dataframe(periods=1, freq='A'); forecast = model.predict(future)
    margin_forecast_val = forecast.iloc[-1]['yhat']
    
    if plot:
        try: 
            fig = model.plot(forecast)
            plt.plot(df_margin['ds'], df_margin['y'], 'o-', label='Historical Margin')
            plt.title(f"{symbol} Operating Margin Forecast (Best CPS: {best_cps:.2f})")
            plt.xlabel("Year")
            plt.ylabel("Operating Margin (%)")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plot_data = plot_to_base64(fig)
        except Exception as e: print(f"Error plotting operating margin for {symbol}: {e}")

    print(f"Operating Margin Forecast for {symbol}: {margin_forecast_val:.2f}% (CPS: {best_cps})")
    return {'margin_forecast': margin_forecast_val, 'best_cps': best_cps, 'plot_base64': plot_data}

def forecast_revenue_cagr(symbol, api_key, forecast_years=5, history_years=15, cps_grid=None, growth='logistic', plot=True):
    """Forecasts revenue CAGR."""
    print(f"\nForecasting Revenue CAGR for {symbol} over {forecast_years} years (growth: {growth})...")
    if cps_grid is None: cps_grid = [0.05, 0.1, 0.2, 0.3, 0.5]
    df_revenue = get_annual_financial_data(symbol, api_key, "revenue", history_years)

    plot_data = None
    
    if len(df_revenue) < 3: # For train/test split for CPS tuning
        print(f"Not enough revenue history for CAGR tuning ({symbol}, got {len(df_revenue)}).")
        if len(df_revenue) >=2: # Attempt simple historical CAGR
            initial_rev = df_revenue['y'].iloc[0]; final_rev = df_revenue['y'].iloc[-1]
            num_years_hist = (df_revenue['ds'].iloc[-1].year - df_revenue['ds'].iloc[0].year)
            if num_years_hist > 0 and initial_rev > 0:
                hist_cagr = (final_rev / initial_rev) ** (1/num_years_hist) -1
                return {'cagr_forecast': hist_cagr, 'best_cps': 0.05, 'error': "Insufficient data for Prophet, historical CAGR used.", 'plot_base64': plot_data}
        return {'cagr_forecast': 0.0, 'best_cps': 0.05, 'error': "Insufficient data for CAGR", 'plot_base64': plot_data}

    best_cps = 0.05; errors = []
    cap_val = df_revenue['y'].max() * 1.5 if growth == 'logistic' else None
    
    train_df_orig = df_revenue.iloc[:-1].copy()
    if len(train_df_orig) < 2 :
        print(f"Cannot perform CAGR CPS tuning for {symbol} (train data < 2). Using default CPS.")
    else:
        actual_last_year_revenue = df_revenue.iloc[-1]['y']
        for cps_tune_val in cps_grid:
            train_df_iter = train_df_orig.copy() # Use fresh copy for each iteration
            model_tune = Prophet(growth=growth, yearly_seasonality=False, changepoint_prior_scale=cps_tune_val, n_changepoints=min(10, len(train_df_iter)-1))
            if growth == 'logistic': train_df_iter['cap'] = cap_val
            
            model_tune.fit(train_df_iter)
            future_tune = model_tune.make_future_dataframe(periods=1, freq='A')
            if growth == 'logistic': future_tune['cap'] = cap_val
            
            forecast_tune = model_tune.predict(future_tune)
            predicted_last_year_revenue = forecast_tune['yhat'].iloc[-1]
            error = np.abs(predicted_last_year_revenue - actual_last_year_revenue) / actual_last_year_revenue if actual_last_year_revenue != 0 else float('inf')
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
    cagr_forecast_val = ((forecast_end_revenue / initial_revenue) ** (1/forecast_years) - 1) if initial_revenue != 0 and forecast_end_revenue > 0 else 0.0
    
    if plot:
        try: 
            fig = final_model.plot(forecast_final)
            plt.plot(df_revenue['ds'], df_revenue['y'], 'o-', label='Historical Revenue')
            plt.title(f"{symbol} {forecast_years}-Yr Revenue Forecast (Best CPS={best_cps:.2f}, Growth: {growth})")
            plt.xlabel("Year")
            plt.ylabel("Revenue (USD)")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plot_data = plot_to_base64(fig)
        except Exception as e: print(f"Error plotting CAGR forecast for {symbol}: {e}")

    print(f"{forecast_years}-Year Forecasted CAGR for {symbol}: {cagr_forecast_val*100:.2f}% (CPS: {best_cps})")
    return {'cagr_forecast': cagr_forecast_val, 'best_cps': best_cps, 'plot_base64': plot_data}

def forecast_pretarget_operating_margin(symbol, api_key, history_years=5, plot=True):
    """Forecasts target operating margin and convergence."""
    print(f"\nForecasting Pre-Target Operating Margin & Convergence for {symbol}...")
    df_margin = get_annual_financial_data(symbol, api_key, "operating_margin", history_years=max(history_years, 5))

    plot_data = None
    
    if len(df_margin) < 2: # Need at least 2 points for linear regression
        print(f"Not enough historical margin data for trend ({symbol}, got {len(df_margin)}).")
        return {'target_margin': 0.0, 'years_to_converge': np.inf, 'error': "Insufficient data", 'plot_base64': plot_data}

    recent_margins = df_margin.tail(history_years) 
    if len(recent_margins) < 2:
        current_margin_val = df_margin['y'].iloc[-1] if not df_margin.empty else 0.0
        print(f"Not enough recent margin data for linear trend ({symbol}). Using last margin as target.")
        return {'current_margin': current_margin_val, 'target_margin': current_margin_val, 'annual_change_pct_points': 0.0, 'years_to_converge': 0.0, 'plot_base64': plot_data}

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
            fig = plt.figure(figsize=(10, 6))
            plt.plot(recent_margins['ds'].dt.year, y, 'o-', label='Historical Operating Margin (%)')
            plt.plot(X, model.predict(X), '--', label='Linear Regression Trend')
            plt.axvline(future_year_for_target, color='red', linestyle=':', label=f'Target Year ({future_year_for_target})')
            plt.scatter(future_year_for_target, target_margin_forecast, color='red', zorder=5)
            plt.text(future_year_for_target, target_margin_forecast, f' Target: {target_margin_forecast:.2f}%', va='bottom', ha='right')
            plt.title(f'{symbol} Operating Margin Trend & Target')
            plt.xlabel('Year')
            plt.ylabel('Operating Margin (%)')
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plot_data = plot_to_base64(fig)
        except Exception as e: print(f"Error plotting pre-target operating margin for {symbol}: {e}")

    print(f"Target Pre-Tax Operating Margin for {symbol} (to {future_year_for_target}): {target_margin_forecast:.2f}%")
    print(f"Years to Converge: {years_to_converge_val:.1f} (Current: {current_margin:.2f}%, Slope: {slope:.2f}%/yr)")
    return {'current_margin': current_margin, 'target_margin': target_margin_forecast, 'annual_change_pct_points': slope, 'years_to_converge': years_to_converge_val, 'plot_base64': plot_data}

def forecast_sales_to_capital_ratio(symbol, api_key, history_years=15, cps=0.05, plot=True):
    """Forecasts sales-to-capital ratio."""
    print(f"\nForecasting Sales-to-Capital Ratio for {symbol}...")
    income_df_raw = get_annual_financial_data(symbol, api_key, "revenue", history_years)
    
    plot_data = None
    
    if income_df_raw.empty:
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "No income data for S/C ratio", 'plot_base64': plot_data}
    income_df = income_df_raw.rename(columns={'y':'totalRevenue'})

    balance_sheet_data = get_alpha_vantage_data("BALANCE_SHEET", symbol, api_key)
    if not balance_sheet_data.get("annualReports"):
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "No balance sheet data for S/C ratio", 'plot_base64': plot_data}
    
    bal_records = []
    for report in balance_sheet_data["annualReports"]:
        bal_records.append({
            "ds": pd.to_datetime(report.get("fiscalDateEnding")),
            "investedCapital": safe_float(report.get("totalAssets")) # Proxy
        })
    balance_df = pd.DataFrame(bal_records).sort_values("ds").reset_index(drop=True)
    if balance_df.empty:
         return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "Processed balance sheet data empty for S/C ratio", 'plot_base64': plot_data}

    df = pd.merge(income_df, balance_df, on='ds', how='inner')
    df.dropna(subset=['totalRevenue', 'investedCapital'], inplace=True)
    if df.empty or df['investedCapital'].eq(0).all():
        return {'avg_1_5': 0.0, 'avg_6_10': 0.0, 'error': "Insufficient merged data for S/C ratio", 'plot_base64': plot_data}
        
    df['ratio'] = df['totalRevenue'] / df['investedCapital']
    df_prophet = df[['ds', 'ratio']].rename(columns={'ratio': 'y'})
    
    if len(df_prophet) < 2:
        avg_hist_ratio = df_prophet['y'].mean() if not df_prophet.empty else 0.0
        return {'avg_1_5': avg_hist_ratio, 'avg_6_10': avg_hist_ratio, 'error': "Insufficient S/C data for Prophet", 'plot_base64': plot_data}

    model = Prophet(yearly_seasonality=False, changepoint_prior_scale=cps, n_changepoints=min(5, len(df_prophet)-1))
    model.fit(df_prophet)
    future = model.make_future_dataframe(periods=10, freq='A')
    fc = model.predict(future)

    last_hist_date = df_prophet['ds'].max()
    forecast_points = fc[fc['ds'] > last_hist_date].reset_index(drop=True)

    if forecast_points.empty or len(forecast_points) < 1:
        avg_hist_ratio = df_prophet['y'].mean() if not df_prophet.empty else 0.0
        return {'avg_1_5': avg_hist_ratio, 'avg_6_10': avg_hist_ratio, 'error': "S/C Prophet forecast produced no future points", 'plot_base64': plot_data}

    avg_1_5_val = forecast_points.loc[0:min(4, len(forecast_points)-1), 'yhat'].mean()
    avg_6_10_val = forecast_points.loc[5:min(9, len(forecast_points)-1), 'yhat'].mean() if len(forecast_points) > 5 else avg_1_5_val

    if plot:
        try: 
            fig = model.plot(fc)
            plt.plot(df_prophet['ds'], df_prophet['y'], 'o-', label='Historical S/C Ratio')
            plt.title(f"{symbol} Sales-to-Capital Ratio Forecast (CPS: {cps:.2f})")
            plt.xlabel("Year")
            plt.ylabel("Sales / Invested Capital")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plot_data = plot_to_base64(fig)
        except Exception as e: print(f"Error plotting S/C ratio for {symbol}: {e}")
    
    print(f"Sales-to-Capital (Years 1–5 avg forecast) for {symbol}: {avg_1_5_val:.2f}")
    print(f"Sales-to-Capital (Years 6–10 avg forecast) for {symbol}: {avg_6_10_val:.2f}")
    return {'avg_1_5': avg_1_5_val, 'avg_6_10': avg_6_10_val, 'plot_base64': plot_data} 