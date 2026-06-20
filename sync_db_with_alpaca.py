import sqlite3
import pandas as pd
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# Fetch Alpaca Positions
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

alpaca_positions = {}
alpaca_prices = {}
try:
    for p in trading_client.get_all_positions():
        alpaca_positions[p.symbol] = float(p.qty)
        alpaca_prices[p.symbol] = {
            'avg_entry': float(p.avg_entry_price),
            'current': float(p.current_price)
        }
except Exception as e:
    print(f"Alpaca API Error: {e}")
    exit(1)

# Fetch Local DB Positions
db_positions = {}
db_avg_cost = {}

try:
    conn = sqlite3.connect("trading_agent.db")
    df = pd.read_sql_query("SELECT ticker, action, share_qty, execution_price FROM transactions ORDER BY timestamp", conn)
    for _, row in df.iterrows():
        ticker = row['ticker']
        action = row['action']
        qty = float(row['share_qty'])
        price = float(row['execution_price'])
        
        if ticker not in db_positions:
            db_positions[ticker] = 0.0
            db_avg_cost[ticker] = 0.0
            
        if action == 'BUY':
            total_cost = (db_positions[ticker] * db_avg_cost[ticker]) + (qty * price)
            db_positions[ticker] += qty
            db_avg_cost[ticker] = total_cost / db_positions[ticker] if db_positions[ticker] > 0 else 0
        elif action == 'SELL':
            db_positions[ticker] -= qty
            if db_positions[ticker] <= 0.0001:
                db_positions[ticker] = 0.0
                db_avg_cost[ticker] = 0.0
except Exception as e:
    print(f"DB Error: {e}")
    exit(1)

# Clean up zero positions from DB
db_positions = {k: v for k, v in db_positions.items() if v > 0.0001}

all_tickers = set(alpaca_positions.keys()).union(set(db_positions.keys()))
cursor = conn.cursor()

injected_count = 0
for ticker in all_tickers:
    alp_qty = alpaca_positions.get(ticker, 0.0)
    db_qty = db_positions.get(ticker, 0.0)
    
    delta = alp_qty - db_qty
    if abs(delta) > 0.0001:
        # We need to inject a sync trade
        action = 'BUY' if delta > 0 else 'SELL'
        qty = abs(delta)
        
        # Determine price
        if ticker in alpaca_prices:
            price = alpaca_prices[ticker]['avg_entry'] if action == 'BUY' else alpaca_prices[ticker]['current']
        else:
            price = db_avg_cost.get(ticker, 100.0) # Fallback
        
        order_id = str(uuid.uuid4())
        from datetime import timezone
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        cursor.execute('''
            INSERT INTO transactions (alpaca_order_id, ticker, action, share_qty, execution_price, timestamp, order_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, ticker, action, qty, price, timestamp, 'market', 'filled'))
        print(f"INJECTED: {action} {qty:.4f} {ticker} @ ${price:.2f} to sync with Alpaca.")
        injected_count += 1
        
        # Update active_positions table to reflect new reality
        if alp_qty > 0.0001:
            # Ensure it is in active_positions
            cursor.execute("SELECT * FROM active_positions WHERE ticker=?", (ticker,))
            if not cursor.fetchone():
                current_p = alpaca_prices[ticker]['current']
                cursor.execute('''
                    INSERT INTO active_positions (ticker, highest_tracked_price, dynamic_stop_percent)
                    VALUES (?, ?, ?)
                ''', (ticker, current_p, 0.08))
        else:
            # Ensure it is NOT in active_positions
            cursor.execute("DELETE FROM active_positions WHERE ticker=?", (ticker,))

# Make sure all Alpaca positions are tracked in active_positions even if DB matched qty
for ticker, qty in alpaca_positions.items():
    if qty > 0.0001:
        cursor.execute("SELECT * FROM active_positions WHERE ticker=?", (ticker,))
        if not cursor.fetchone():
            current_p = alpaca_prices[ticker]['current']
            cursor.execute('''
                INSERT INTO active_positions (ticker, highest_tracked_price, dynamic_stop_percent)
                VALUES (?, ?, ?)
            ''', (ticker, current_p, 0.08))

conn.commit()
conn.close()

if injected_count == 0:
    print("SYNC COMPLETE: No discrepancies found.")
else:
    print(f"SYNC COMPLETE: Injected {injected_count} synthetic transactions to balance the DB ledger.")
