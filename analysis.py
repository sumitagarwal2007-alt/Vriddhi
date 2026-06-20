import sqlite3
import pandas as pd

conn = sqlite3.connect('trading_agent.db')

# Analyze Trade Feedback for Realized Losses
df = pd.read_sql_query("SELECT * FROM trade_feedback", conn)
if not df.empty:
    df['pnl_dollar'] = (df['sell_price'] - df['buy_price']) * 1 # rough metric
    losses = df[df['pnl_pct'] < 0].sort_values('pnl_pct')
    
    print("=== BIGGEST LOSERS BY PERCENTAGE ===")
    print(losses[['ticker', 'pnl_pct', 'significance_score', 'reasoning']].head(5))
    
    print("\n=== WIN RATE BY SIGNIFICANCE ===")
    for sig in df['significance_score'].unique():
        sig_df = df[df['significance_score'] == sig]
        win_rate = (sig_df['pnl_pct'] > 0).mean() * 100
        print(f"Score {sig}: {win_rate:.1f}% win rate ({len(sig_df)} trades)")

# Analyze Ledger for actual Realized Dollar Losses
tx = pd.read_sql_query("SELECT * FROM transactions ORDER BY timestamp ASC", conn)
open_pos = {}
asset_pnl = {}
for _, row in tx.iterrows():
    t = row['ticker']
    if t not in open_pos: open_pos[t] = {'qty': 0.0, 'cost': 0.0}
    if t not in asset_pnl: asset_pnl[t] = 0.0
    
    q = float(row['share_qty'])
    p = float(row['execution_price'])
    
    if row['action'] == 'BUY':
        open_pos[t]['qty'] += q
        open_pos[t]['cost'] += q * p
    elif row['action'] == 'SELL':
        if open_pos[t]['qty'] > 0:
            avg_cost = open_pos[t]['cost'] / open_pos[t]['qty']
            realized = (p - avg_cost) * q
            asset_pnl[t] += realized
            open_pos[t]['qty'] -= q
            open_pos[t]['cost'] -= avg_cost * q

pnl_df = pd.DataFrame([{'ticker': k, 'pnl': v} for k, v in asset_pnl.items() if v != 0])
if not pnl_df.empty:
    worst = pnl_df.sort_values('pnl').head(10)
    print("\n=== WORST ASSETS BY REALIZED $ LOSS ===")
    print(worst.to_string(index=False))

# Active positions paper losses
print("\n=== WORST ACTIVE (PAPER) LOSSES ===")
active = pd.read_sql_query("SELECT * FROM active_positions", conn)
# We can't fetch live prices here easily without md.get_live_price, but we can see purchase prices vs highest
print(active[['ticker', 'purchase_price', 'highest_tracked_price', 'dynamic_stop_percent']].head())

conn.close()
