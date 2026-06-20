import sqlite3
import pandas as pd
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# 1. Fetch Alpaca Positions
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

alpaca_positions = {}
try:
    for p in trading_client.get_all_positions():
        alpaca_positions[p.symbol] = float(p.qty)
except Exception as e:
    print(f"Alpaca API Error: {e}")
    exit(1)

# 2. Fetch Local DB Positions
db_positions = {}
try:
    conn = sqlite3.connect("trading_agent.db")
    df = pd.read_sql_query("SELECT ticker, action, share_qty FROM transactions ORDER BY timestamp", conn)
    for _, row in df.iterrows():
        ticker = row['ticker']
        action = row['action']
        qty = float(row['share_qty'])
        
        if ticker not in db_positions:
            db_positions[ticker] = 0.0
            
        if action == 'BUY':
            db_positions[ticker] += qty
        elif action == 'SELL':
            db_positions[ticker] -= qty
            if db_positions[ticker] <= 0.0001:
                db_positions[ticker] = 0.0
    conn.close()
except Exception as e:
    print(f"DB Error: {e}")
    exit(1)

# Clean up zero positions from DB
db_positions = {k: v for k, v in db_positions.items() if v > 0.0001}

# 3. Compare
all_tickers = set(alpaca_positions.keys()).union(set(db_positions.keys()))
discrepancies = []

for ticker in all_tickers:
    alp_qty = alpaca_positions.get(ticker, 0.0)
    db_qty = db_positions.get(ticker, 0.0)
    if abs(alp_qty - db_qty) > 0.0001:
        discrepancies.append((ticker, db_qty, alp_qty))

if not discrepancies:
    print("SYNC OK: Local DB matches Alpaca exactly!")
else:
    print("DISCREPANCIES FOUND:")
    print(f"{'Ticker':<10} | {'Local DB Qty':<15} | {'Alpaca Qty':<15}")
    print("-" * 46)
    for t, db_q, alp_q in discrepancies:
        print(f"{t:<10} | {db_q:<15.4f} | {alp_q:<15.4f}")
