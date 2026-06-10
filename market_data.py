import os
import requests
import pandas as pd
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

SP500_TICKERS = set()

def load_sp500_universe():
    global SP500_TICKERS
    print("[Gateway YUKTI] Auto-scraping S&P 500 constituents...")
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        from io import StringIO
        tables = pd.read_html(StringIO(response.text))
        df = tables[0]
        # Clean up tickers that might have '.' instead of '-' (e.g. BRK.B to BRK-B) if necessary, 
        # but typical news uses basic tickers.
        SP500_TICKERS = set(df['Symbol'].str.replace('.', '-', regex=False).tolist())
        print(f"[Gateway YUKTI] Successfully loaded {len(SP500_TICKERS)} tickers.")
    except Exception as e:
        print(f"[Gateway YUKTI] Error scraping S&P 500: {e}")

def is_eligible(ticker: str) -> bool:
    if not SP500_TICKERS:
        load_sp500_universe()
    return ticker in SP500_TICKERS

def _safe_get(url: str, retries: int = 3, delay: float = 1.0) -> Optional[requests.Response]:
    import time
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=5.0)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                # Rate limited, back off longer
                time.sleep(delay * 2 * (attempt + 1))
            else:
                print(f"[Gateway YUKTI] HTTP Error {resp.status_code} on attempt {attempt+1}")
        except requests.RequestException as e:
            print(f"[Gateway YUKTI] Connection error on attempt {attempt+1}: {e}")
        time.sleep(delay * (attempt + 1))
    return None

def get_live_price(ticker: str) -> float:
    """Fetch live price via Finnhub REST endpoint."""
    token = os.getenv("FINNHUB_TOKEN")
    if not token or token == "YOUR_FINNHUB_KEY":
        # Return mock price for diagnostic runs
        print(f"[Gateway YUKTI] Mocking price for {ticker} (Finnhub token missing)")
        return 150.0

    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={token}"
    resp = _safe_get(url)
    if resp is not None:
        try:
            data = resp.json()
            return float(data.get('c', 0.0) or 0.0)
        except Exception as e:
            print(f"[Gateway YUKTI] JSON parsing error for {ticker}: {e}")
    return 0.0

def calculate_dynamic_stop(ticker: str, current_price: float) -> float:
    """
    Fetch daily price range to determine volatility.
    If highly volatile, wider 5.0% stop.
    If stable large-cap anchor, tighter 2.5% stop.
    """
    token = os.getenv("FINNHUB_TOKEN")
    if not token or token == "YOUR_FINNHUB_KEY":
        return 0.025 # Default tight stop

    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={token}"
    resp = _safe_get(url)
    if resp is not None:
        try:
            data = resp.json()
            high = float(data.get('h', 0.0) or 0.0)
            low = float(data.get('l', 0.0) or 0.0)
            if high > 0 and low > 0:
                volatility_pct = (high - low) / low
                if volatility_pct > 0.03: # >3% intraday range
                    return 0.05
        except Exception as e:
            print(f"[Gateway YUKTI] JSON parsing error for {ticker} volatility: {e}")
    return 0.025

def get_spy_performance() -> float:
    """Returns the daily percentage change of SPY."""
    token = os.getenv("FINNHUB_TOKEN")
    if not token or token == "YOUR_FINNHUB_KEY":
        return 0.0

    url = f"https://finnhub.io/api/v1/quote?symbol=SPY&token={token}"
    resp = _safe_get(url)
    if resp is not None:
        try:
            data = resp.json()
            current = float(data.get('c', 0.0) or 0.0)
            previous_close = float(data.get('pc', 0.0) or 0.0)
            if current > 0 and previous_close > 0:
                return (current - previous_close) / previous_close
        except Exception as e:
            print(f"[Gateway YUKTI] JSON parsing error for SPY: {e}")
    return 0.0

def get_vixy_change() -> float:
    """Returns the daily percentage change of VIXY (VIX ETF) to measure fear."""
    token = os.getenv("FINNHUB_TOKEN")
    if not token or token == "YOUR_FINNHUB_KEY":
        return 0.0

    url = f"https://finnhub.io/api/v1/quote?symbol=VIXY&token={token}"
    resp = _safe_get(url)
    if resp is not None:
        try:
            data = resp.json()
            current = float(data.get('c', 0.0) or 0.0)
            previous_close = float(data.get('pc', 0.0) or 0.0)
            if current > 0 and previous_close > 0:
                return (current - previous_close) / previous_close
        except Exception as e:
            print(f"[Gateway YUKTI] JSON parsing error for VIXY: {e}")
    return 0.0

def calculate_position_size(stop_percent: float, significance_score: int = 7, portfolio_equity: float = 10000.0, spy_momentum: float = 0.0) -> float:
    """
    Dynamic Fractional Risk Model (V3 Upgrade).
    Base risk is 0.2% of active portfolio equity (defaults to $20 if equity is small).
    Adjusted by:
      - AI Significance Score (Score >= 9: 1.5x risk; Score 7-8: 1.0x risk; Score < 7: 0.5x risk)
      - SPY Momentum (SPY > +0.2%: 1.2x risk; SPY < -0.2%: 0.8x risk)
    Position Size = Risk / Stop_Percent
    """
    # 1. Determine base risk amount (0.2% of equity, min $20)
    base_risk = max(20.0, portfolio_equity * 0.002)
    
    # 2. Score multiplier
    if significance_score >= 9:
        score_mult = 1.5
    elif significance_score >= 7:
        score_mult = 1.0
    else:
        score_mult = 0.5
        
    # 3. SPY Momentum multiplier
    if spy_momentum >= 0.002:
        spy_mult = 1.2
    elif spy_momentum <= -0.002:
        spy_mult = 0.8
    else:
        spy_mult = 1.0
        
    risk_amount = base_risk * score_mult * spy_mult
    
    if stop_percent <= 0:
        return max(100.0, min(1200.0, portfolio_equity * 0.05)) # fallback
        
    size = risk_amount / stop_percent
    
    # Cap size between $100 and $1200 (or up to 10% of portfolio equity)
    max_size = max(1200.0, min(2000.0, portfolio_equity * 0.10))
    return max(100.0, min(max_size, size))
