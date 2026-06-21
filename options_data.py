import yfinance as yf
import pandas as pd
from datetime import datetime, date
import math

try:
    from py_vollib.black_scholes_merton.greeks.analytical import delta, gamma, rho, theta, vega
except ImportError:
    pass # Fallback to dummy if py_vollib fails

def get_risk_free_rate():
    # Roughly use 3-month treasury bill yield (^IRX)
    try:
        irx = yf.Ticker("^IRX")
        history = irx.history(period="1d")
        if not history.empty:
            rate = history['Close'].iloc[-1] / 100.0
            return max(0.01, rate)
    except:
        pass
    return 0.045 # Fallback to 4.5%

def compute_greeks(flag, S, K, t, r, sigma, q=0.0):
    """
    flag: 'c' for call, 'p' for put
    S: underlying spot price
    K: strike price
    t: time to expiration in years
    r: risk-free rate
    sigma: implied volatility
    q: continuous dividend yield (assumed 0)
    """
    if t <= 0 or sigma <= 0:
        return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
        
    try:
        d = delta(flag, S, K, t, r, sigma, q)
        g = gamma(flag, S, K, t, r, sigma, q)
        th = theta(flag, S, K, t, r, sigma, q)
        v = vega(flag, S, K, t, r, sigma, q)
        rh = rho(flag, S, K, t, r, sigma, q)
        return {'delta': d, 'gamma': g, 'theta': th, 'vega': v, 'rho': rh}
    except Exception as e:
        return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}

def get_leaps_options_chain(ticker_symbol: str, min_days_to_expiration: int = 45):
    """
    Fetches the options chain for a given ticker for expirations >= min_days_to_expiration.
    Returns a dataframe of Call options enriched with Greeks.
    """
    ticker = yf.Ticker(ticker_symbol)
    spot_history = ticker.history(period="1d")
    if spot_history.empty:
        return pd.DataFrame()
        
    spot_price = spot_history['Close'].iloc[-1]
    risk_free_rate = get_risk_free_rate()
    today = date.today()
    
    all_calls = []
    
    # Loop over available expirations
    for exp_str in ticker.options:
        exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
        days_to_exp = (exp_date - today).days
        
        if days_to_exp < min_days_to_expiration:
            continue
            
        t_years = days_to_exp / 365.0
        chain = ticker.option_chain(exp_str)
        calls = chain.calls
        
        for idx, row in calls.iterrows():
            strike = row['strike']
            iv = row['impliedVolatility']
            bid = row['bid']
            ask = row['ask']
            volume = row['volume']
            open_interest = row['openInterest']
            
            # Compute Greeks if IV is available and valid
            if pd.notna(iv) and iv > 0.01:
                greeks = compute_greeks('c', spot_price, strike, t_years, risk_free_rate, iv)
            else:
                greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
                
            all_calls.append({
                'ticker': ticker_symbol,
                'expiration': exp_str,
                'days_to_exp': days_to_exp,
                'strike': strike,
                'spot_price': spot_price,
                'bid': bid,
                'ask': ask,
                'volume': volume,
                'open_interest': open_interest,
                'iv': iv,
                'delta': greeks['delta'],
                'gamma': greeks['gamma'],
                'theta': greeks['theta'],
                'vega': greeks['vega']
            })
            
    df = pd.DataFrame(all_calls)
    return df

def get_market_context():
    """
    Fetches VIX and SPY to create a simple Macro Context dictionary.
    """
    vix = yf.Ticker("^VIX").history(period="1d")
    spy = yf.Ticker("SPY").history(period="5d")
    
    vix_close = vix['Close'].iloc[-1] if not vix.empty else 15.0
    
    spy_current = spy['Close'].iloc[-1] if not spy.empty else 500.0
    spy_prev = spy['Close'].iloc[0] if not spy.empty else 500.0
    spy_trend = (spy_current - spy_prev) / spy_prev
    
    # Simple macro score based on VIX
    # VIX < 15: Bullish (8-10)
    # VIX 15-20: Neutral (5-7)
    # VIX > 20: Bearish / High Vol (1-4)
    if vix_close < 15:
        macro_score = 8
        env = "Low Volatility / Bullish"
    elif vix_close <= 20:
        macro_score = 5
        env = "Moderate Volatility / Neutral"
    else:
        macro_score = 2
        env = "High Volatility / Bearish"
        
    return {
        "VIX": round(vix_close, 2),
        "SPY_5D_Trend": round(spy_trend * 100, 2),
        "Macro_Score": macro_score,
        "Environment": env
    }
