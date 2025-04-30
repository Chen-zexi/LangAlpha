import pandas as pd
import numpy as np
from typing import Dict, Any


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average for a given period"""
    return data.ewm(span=period, adjust=False).mean()

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index (ADX)"""
    # Calculate +DM, -DM, +DI, -DI, and TR
    high = df['high']
    low = df['low']
    close = df['close']
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    # Directional Movement
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm = plus_dm.where((plus_dm > 0) & (plus_dm > minus_dm.abs()), 0)
    minus_dm = minus_dm.abs().where((minus_dm < 0) & (plus_dm < minus_dm.abs()), 0)
    
    # Directional Indicators
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    
    # Directional Index
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    
    return adx

def calculate_trend_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate trend following signals using EMAs and ADX
    
    Args:
        df: DataFrame containing price data (must have columns: close, high, low)
    
    Returns:
        Dictionary with trend signal information
    """
    if df.empty:
        return {
            "strategy": "Trend Following",
            "signal": "neutral",
            "confidence": 0,
            "error": "No data available"
        }
    
    # Calculate EMAs
    df['ema8'] = calculate_ema(df['close'], 8)
    df['ema21'] = calculate_ema(df['close'], 21)
    df['ema55'] = calculate_ema(df['close'], 55)
    df['ema200'] = calculate_ema(df['close'], 200)  # Added 200 EMA based on feedback
    
    # Calculate ADX
    df['adx'] = calculate_adx(df)
    
    # Determine short and medium term trends
    df['short_trend'] = np.where(df['ema8'] > df['ema21'], 1, -1)
    df['medium_trend'] = np.where(df['ema21'] > df['ema55'], 1, -1)
    df['long_trend'] = np.where(df['close'] > df['ema200'], 1, -1)  # Added long-term trend context
    
    # Get latest data
    latest = df.iloc[-1]
    
    # Determine signal with ADX threshold (based on feedback)
    adx_value = latest['adx']
    adx_threshold = 20  # Standard threshold per feedback
    
    if latest['short_trend'] == 1 and latest['medium_trend'] == 1 and adx_value >= adx_threshold:
        signal = "bullish"
    elif latest['short_trend'] == -1 and latest['medium_trend'] == -1 and adx_value >= adx_threshold:
        signal = "bearish"
    else:
        signal = "neutral"
    
    # Determine confidence based on ADX strength
    if pd.isna(adx_value):
        confidence = 0
    else:
        # ADX < 20: weak trend, ADX > 40: strong trend
        if adx_value < 20:
            confidence = adx_value / 20  # 0 to 1
        elif adx_value < 40:
            confidence = 1 + (adx_value - 20) / 20  # 1 to 2
        else:
            confidence = 2 + (adx_value - 40) / 20  # 2 to 3 (capped at 3 for ADX>=60)
            confidence = min(confidence, 3)
    
    return {
        "strategy": "Trend Following",
        "signal": signal,
        "confidence": round(confidence, 2),
        "metrics": {
            "ema8": round(latest['ema8'], 2),
            "ema21": round(latest['ema21'], 2),
            "ema55": round(latest['ema55'], 2),
            "ema200": round(latest['ema200'], 2),
            "adx": round(adx_value if not pd.isna(adx_value) else 0, 2),
            "short_trend": "up" if latest['short_trend'] == 1 else "down",
            "medium_trend": "up" if latest['medium_trend'] == 1 else "down",
            "long_trend": "up" if latest['long_trend'] == 1 else "down",
            "adx_threshold_met": adx_value >= adx_threshold
        }
    }

def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index"""
    delta = data.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # For subsequent calculations
    for i in range(period, len(delta)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period-1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period-1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_mean_reversion_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate mean reversion signals using Z-score, Bollinger Bands, and RSI
    
    Args:
        df: DataFrame containing price data (must have columns: close)
    
    Returns:
        Dictionary with mean reversion signal information
    """
    if df.empty:
        return {
            "strategy": "Mean Reversion",
            "signal": "neutral",
            "confidence": 0,
            "error": "No data available"
        }
    
    # Calculate 50-period SMA and standard deviation
    df['sma50'] = df['close'].rolling(window=50).mean()
    df['std50'] = df['close'].rolling(window=50).std()
    
    # Calculate Z-score
    df['zscore'] = (df['close'] - df['sma50']) / df['std50']
    
    # Calculate Bollinger Bands (20-period, 2 standard deviations)
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['std20'] = df['close'].rolling(window=20).std()
    df['upper_band'] = df['sma20'] + 2 * df['std20']
    df['lower_band'] = df['sma20'] - 2 * df['std20']
    
    # Calculate RSI for 14 and 28 periods
    df['rsi14'] = calculate_rsi(df['close'], 14)
    df['rsi28'] = calculate_rsi(df['close'], 28)
    
    # Get latest data
    latest = df.iloc[-1]
    
    # Determine signal - tightened Z-score to ±1.5 per feedback
    signal = "neutral"
    confidence = 0
    
    # Check for bullish mean reversion signal
    if (latest['zscore'] < -1.5 and latest['close'] <= latest['lower_band'] and 
        latest['rsi14'] < 30):
        signal = "bullish"
        confidence = min(abs(latest['zscore']) / 1.5, 3)  # Confidence 1-3 based on Z-score
    
    # Check for bearish mean reversion signal
    elif (latest['zscore'] > 1.5 and latest['close'] >= latest['upper_band'] and 
          latest['rsi14'] > 70):
        signal = "bearish"
        confidence = min(abs(latest['zscore']) / 1.5, 3)  # Confidence 1-3 based on Z-score
    
    return {
        "strategy": "Mean Reversion",
        "signal": signal,
        "confidence": round(confidence, 2),
        "metrics": {
            "z_score": round(latest['zscore'], 2),
            "price": round(latest['close'], 2),
            "sma50": round(latest['sma50'], 2),
            "upper_band": round(latest['upper_band'], 2),
            "lower_band": round(latest['lower_band'], 2),
            "rsi14": round(latest['rsi14'], 2),
            "rsi28": round(latest['rsi28'], 2),
            "price_to_sma_ratio": round(latest['close'] / latest['sma50'], 2) if latest['sma50'] > 0 else 0
        }
    }

def rank_normalize(series):
    """
    Convert a series to percentile ranks (0-1)
    """
    return series.rank(pct=True)

def calculate_momentum_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate momentum signals using price and volume momentum metrics
    
    Args:
        df: DataFrame containing price and volume data (must have columns: close, volume)
    
    Returns:
        Dictionary with momentum signal information
    """
    if df.empty:
        return {
            "strategy": "Momentum",
            "signal": "neutral",
            "confidence": 0,
            "error": "No data available"
        }
    
    # Need at least 126 days for 6-month momentum
    if len(df) < 126:  
        return {
            "strategy": "Momentum",
            "signal": "neutral",
            "confidence": 0,
            "error": "Insufficient data for momentum calculation"
        }
    
    # Calculate percentage changes for different periods
    df['pct_change'] = df['close'].pct_change()
    
    # Rolling momentum calculations
    df['mom_1m'] = df['close'].pct_change(21)  # 1-month momentum (21 trading days)
    df['mom_3m'] = df['close'].pct_change(63)  # 3-month momentum (63 trading days)
    df['mom_6m'] = df['close'].pct_change(126)  # 6-month momentum (126 trading days)
    
    # Rank normalize momentum (per feedback)
    df['mom_1m_rank'] = rank_normalize(df['mom_1m'])
    df['mom_3m_rank'] = rank_normalize(df['mom_3m'])
    df['mom_6m_rank'] = rank_normalize(df['mom_6m'])
    
    # Volume momentum - using relative volume (per feedback confirmation)
    df['vol_ma21'] = df['volume'].rolling(window=21).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma21']  # This is already relative volume
    
    # Combined momentum score (weight: 50% for 1M, 30% for 3M, 20% for 6M)
    # Using rank normalized values per feedback
    df['momentum_score'] = (0.5 * df['mom_1m_rank'] + 
                          0.3 * df['mom_3m_rank'] + 
                          0.2 * df['mom_6m_rank'])
    
    # Convert score from 0-1 to -1 to 1 range for directional signals
    df['momentum_score'] = (df['momentum_score'] - 0.5) * 2
    
    # Get latest data
    latest = df.iloc[-1]
    
    # Determine signal
    if latest['momentum_score'] > 0.2 and latest['vol_ratio'] > 1.0:
        signal = "bullish"
        confidence = min(abs(latest['momentum_score']) * 3, 3)  # Scale confidence based on momentum strength
    elif latest['momentum_score'] < -0.2 and latest['vol_ratio'] > 1.0:
        signal = "bearish"
        confidence = min(abs(latest['momentum_score']) * 3, 3)  # Scale confidence based on momentum strength
    else:
        signal = "neutral"
        confidence = 0
    
    return {
        "strategy": "Momentum",
        "signal": signal,
        "confidence": round(confidence, 2),
        "metrics": {
            "momentum_1m": round(latest['mom_1m'] * 100, 2) if not pd.isna(latest['mom_1m']) else 0,
            "momentum_3m": round(latest['mom_3m'] * 100, 2) if not pd.isna(latest['mom_3m']) else 0,
            "momentum_6m": round(latest['mom_6m'] * 100, 2) if not pd.isna(latest['mom_6m']) else 0,
            "momentum_1m_rank": round(latest['mom_1m_rank'], 2) if not pd.isna(latest['mom_1m_rank']) else 0,
            "momentum_3m_rank": round(latest['mom_3m_rank'], 2) if not pd.isna(latest['mom_3m_rank']) else 0,
            "momentum_6m_rank": round(latest['mom_6m_rank'], 2) if not pd.isna(latest['mom_6m_rank']) else 0,
            "combined_score": round(latest['momentum_score'], 2) if not pd.isna(latest['momentum_score']) else 0,
            "volume_ratio": round(latest['vol_ratio'], 2) if not pd.isna(latest['vol_ratio']) else 0
        }
    }

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr

def calculate_volatility_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate volatility-based signals using historical volatility, volatility regime,
    and ATR metrics
    
    Args:
        df: DataFrame containing price data (must have columns: close, high, low)
    
    Returns:
        Dictionary with volatility signal information
    """
    if df.empty:
        return {
            "strategy": "Volatility",
            "signal": "neutral",
            "confidence": 0,
            "error": "No data available"
        }
    
    # Need at least 84 bars (21 + 63) for volatility regime calculation
    if len(df) < 84:
        return {
            "strategy": "Volatility",
            "signal": "neutral",
            "confidence": 0,
            "error": "Insufficient data for volatility calculation"
        }
    
    # Calculate daily returns
    df['returns'] = df['close'].pct_change()
    
    # Calculate 21-day annualized volatility (standard deviation of returns * sqrt(252))
    df['volatility_21d'] = df['returns'].rolling(window=21).std() * np.sqrt(252)
    
    # Calculate 63-day average of volatility
    df['volatility_63d_avg'] = df['volatility_21d'].rolling(window=63).mean()
    
    # Calculate volatility Z-score
    df['volatility_std'] = df['volatility_21d'].rolling(window=63).std()
    df['volatility_zscore'] = (df['volatility_21d'] - df['volatility_63d_avg']) / df['volatility_std']
    
    # Calculate volatility percentile rank (per feedback)
    df['volatility_rank'] = rank_normalize(df['volatility_21d'].rolling(window=63))
    
    # Add rolling z > ±1 bands (per feedback)
    df['vol_above_band'] = (df['volatility_zscore'] > 1).rolling(window=5).mean()
    df['vol_below_band'] = (df['volatility_zscore'] < -1).rolling(window=5).mean()
    
    # Calculate ATR and ATR ratio
    df['atr'] = calculate_atr(df, 14)
    df['atr_ratio'] = df['atr'] / df['close']
    
    # Get latest data
    latest = df.iloc[-1]
    
    # Determine signal - maintain break-out hypothesis but add additional filter for persistence
    if (not pd.isna(latest['volatility_zscore']) and 
        latest['volatility_zscore'] < -1.5 and 
        latest['vol_below_band'] > 0.6):  # Unusually low volatility, potential for expansion
        signal = "bullish"
        confidence = min(abs(latest['volatility_zscore']) / 1.5, 3)
    elif (not pd.isna(latest['volatility_zscore']) and 
          latest['volatility_zscore'] > 1.5 and 
          latest['vol_above_band'] > 0.6):  # Unusually high volatility, potential for contraction
        signal = "bearish"
        confidence = min(abs(latest['volatility_zscore']) / 1.5, 3)
    else:
        signal = "neutral"
        confidence = 0
    
    return {
        "strategy": "Volatility",
        "signal": signal,
        "confidence": round(confidence, 2),
        "metrics": {
            "current_volatility": round(latest['volatility_21d'] * 100, 2) if not pd.isna(latest['volatility_21d']) else 0,
            "average_volatility": round(latest['volatility_63d_avg'] * 100, 2) if not pd.isna(latest['volatility_63d_avg']) else 0,
            "volatility_zscore": round(latest['volatility_zscore'], 2) if not pd.isna(latest['volatility_zscore']) else 0,
            "volatility_percentile": round(latest['volatility_rank'] * 100, 2) if not pd.isna(latest['volatility_rank']) else 0,
            "atr_14d": round(latest['atr'], 2) if not pd.isna(latest['atr']) else 0,
            "atr_to_price_ratio": round(latest['atr_ratio'] * 100, 2) if not pd.isna(latest['atr_ratio']) else 0
        }
    }

def calculate_hurst_exponent(time_series: pd.Series, max_lag: int = 20) -> float:
    """
    Calculate Hurst Exponent to determine if a time series is mean-reverting,
    trending, or random walk
    """
    # Create a range of lag values
    lags = range(2, max_lag)
    
    # Calculate the array of the variances of the lagged differences
    tau = [np.sqrt(np.std(np.subtract(time_series[lag:].values, time_series[:-lag].values))) for lag in lags]
    
    # Calculate the slope of the log plot -> the Hurst Exponent
    reg = np.polyfit(np.log(lags), np.log(tau), 1)
    
    return reg[0]

def calculate_stat_arb_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate statistical arbitrage signals using return distribution analysis and
    the Hurst exponent
    
    Args:
        df: DataFrame containing price data (must have columns: close)
    
    Returns:
        Dictionary with statistical arbitrage signal information
    """
    if df.empty:
        return {
            "strategy": "Statistical Arbitrage",
            "signal": "neutral",
            "confidence": 0,
            "error": "No data available"
        }
    
    # Need at least 126 bars for reliable Hurst exponent
    if len(df) < 126:
        return {
            "strategy": "Statistical Arbitrage",
            "signal": "neutral",
            "confidence": 0,
            "error": "Insufficient data for statistical analysis"
        }
    
    # Calculate returns
    df['returns'] = df['close'].pct_change()
    
    # Annualize returns for interpretable skew/kurtosis (per feedback)
    df['annualized_returns'] = df['returns'] * np.sqrt(252)
    
    # Calculate rolling skewness and kurtosis with 63-day window
    df['skew_63d'] = df['annualized_returns'].rolling(window=63).skew()
    df['kurt_63d'] = df['annualized_returns'].rolling(window=63).kurt()
    
    # Calculate Hurst exponent - using more data for stability
    # We'll calculate it once for the whole period rather than rolling
    latest_returns = df['returns'].dropna()
    hurst = calculate_hurst_exponent(latest_returns) if len(latest_returns) >= 20 else 0.5
    
    # Get latest data
    latest = df.iloc[-1]
    
    # Determine signal based on Hurst exponent and skewness
    signal = "neutral"
    confidence = 0
    
    if hurst < 0.4:  # Strong mean-reversion characteristics
        if latest['skew_63d'] > 0.5:  # Positive skew (more extreme positive returns)
            signal = "bullish"
            confidence = (0.5 - hurst) * 10  # More confidence as H gets closer to 0
        elif latest['skew_63d'] < -0.5:  # Negative skew (more extreme negative returns)
            signal = "bearish"
            confidence = (0.5 - hurst) * 10  # More confidence as H gets closer to 0
    
    # Cap confidence at 3
    confidence = min(confidence, 3)
    
    return {
        "strategy": "Statistical Arbitrage",
        "signal": signal,
        "confidence": round(confidence, 2),
        "metrics": {
            "hurst_exponent": round(hurst, 2),
            "skewness": round(latest['skew_63d'], 2) if not pd.isna(latest['skew_63d']) else 0,
            "kurtosis": round(latest['kurt_63d'], 2) if not pd.isna(latest['kurt_63d']) else 0,
            "interpretation": (
                "Mean-reverting" if hurst < 0.4 else
                "Random walk" if 0.4 <= hurst <= 0.6 else
                "Trending"
            )
        }
    }

def get_combined_signals(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate signals from all strategies and combine them into a consensus view
    
    Args:
        df: DataFrame containing price and volume data (must have columns: close, high, low, volume)
    
    Returns:
        Dictionary with all strategy signals and consensus signal
    """
    # Calculate all strategy signals
    trend_signals = calculate_trend_signals(df)
    mean_reversion_signals = calculate_mean_reversion_signals(df)
    momentum_signals = calculate_momentum_signals(df)
    volatility_signals = calculate_volatility_signals(df)
    stat_arb_signals = calculate_stat_arb_signals(df)
    
    # Combine all signals
    all_signals = [
        trend_signals,
        mean_reversion_signals,
        momentum_signals,
        volatility_signals,
        stat_arb_signals
    ]
    
    # Calculate bullish and bearish scores
    bullish_score = sum(
        s["confidence"] for s in all_signals if s["signal"] == "bullish"
    )
    
    bearish_score = sum(
        s["confidence"] for s in all_signals if s["signal"] == "bearish"
    )
    
    # Determine consensus signal
    if bullish_score > bearish_score:
        consensus_signal = "bullish"
        consensus_confidence = bullish_score / 15  # Max possible is 3*5=15
    elif bearish_score > bullish_score:
        consensus_signal = "bearish"
        consensus_confidence = bearish_score / 15
    else:
        consensus_signal = "neutral"
        consensus_confidence = 0
    
    # Cap confidence at 1.0
    consensus_confidence = min(consensus_confidence, 1.0)
    
    
    return {
        "strategies": {
            "trend_following": trend_signals,
            "mean_reversion": mean_reversion_signals,
            "momentum": momentum_signals,
            "volatility": volatility_signals,
            "statistical_arbitrage": stat_arb_signals
        },
        "consensus": {
            "signal": consensus_signal,
            "confidence": round(consensus_confidence, 2),
            "bullish_score": round(bullish_score, 2),
            "bearish_score": round(bearish_score, 2)
        }
    }