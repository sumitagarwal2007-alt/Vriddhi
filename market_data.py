import os
import requests
import pandas as pd
from dotenv import load_dotenv

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

def get_live_price(ticker: str) -> float:
    """Fetch live price via Finnhub REST endpoint."""
    token = os.getenv("FINNHUB_TOKEN")
    if not token or token == "YOUR_FINNHUB_KEY":
        # Return mock price for diagnostic runs
        print(f"[Gateway YUKTI] Mocking price for {ticker} (Finnhub token missing)")
        return 150.0

    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={token}"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        return float(data.get('c', 0.0))
    else:
        print(f"[Gateway YUKTI] Finnhub error: {resp.text}")
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
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        high = float(data.get('h', 0.0) or 0.0)
        low = float(data.get('l', 0.0) or 0.0)
        if high > 0 and low > 0:
            volatility_pct = (high - low) / low
            if volatility_pct > 0.03: # >3% intraday range
                return 0.05
    return 0.025
