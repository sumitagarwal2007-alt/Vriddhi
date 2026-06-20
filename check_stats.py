import sqlite3
import pandas as pd

conn = sqlite3.connect("trading_agent.db")
df = pd.read_sql_query("SELECT * FROM transactions", conn)

buys = df[df['action'] == 'BUY']
sells = df[df['action'] == 'SELL']
realized = 0.0

if not buys.empty and not sells.empty:
    merged = pd.merge(buys, sells, on='ticker', suffixes=('_buy', '_sell'))
    if not merged.empty:
        merged['realized_pl'] = (merged['execution_price_sell'] - merged['execution_price_buy']) * merged['share_qty_buy']
        realized = merged['realized_pl'].sum()

print(f"Transactions Realized P/L: {realized}")

df_tf = pd.read_sql_query("SELECT * FROM trade_feedback", conn)
print(f"Trade feedback length: {len(df_tf)}")
if not df_tf.empty:
    wins = (df_tf['pnl_pct'] > 0).sum()
    print(f"Wins: {wins}, Win Rate: {wins/len(df_tf)*100}%")

conn.close()
