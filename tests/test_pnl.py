import sqlite3
import pandas as pd

conn = sqlite3.connect("trading_agent.db")
df = pd.read_sql_query("SELECT * FROM transactions ORDER BY timestamp ASC", conn)
conn.close()

realized_pnl = 0.0
open_positions = {} # ticker -> {qty, total_cost}

for _, row in df.iterrows():
    ticker = row['ticker']
    action = row['action']
    qty = float(row['share_qty'])
    price = float(row['execution_price'])
    
    if ticker not in open_positions:
        open_positions[ticker] = {'qty': 0.0, 'total_cost': 0.0}
        
    pos = open_positions[ticker]
    
    if action == 'BUY':
        pos['qty'] += qty
        pos['total_cost'] += qty * price
    elif action == 'SELL':
        # Assuming we sell the entire position, or a partial. 
        # Calculate cost basis per share
        if pos['qty'] > 0:
            avg_cost = pos['total_cost'] / pos['qty']
            pnl = (price - avg_cost) * qty
            realized_pnl += pnl
            pos['qty'] -= qty
            pos['total_cost'] -= avg_cost * qty
            if pos['qty'] <= 0.0001:
                pos['qty'] = 0.0
                pos['total_cost'] = 0.0

print(f"Computed Realized PNL: {realized_pnl}")
