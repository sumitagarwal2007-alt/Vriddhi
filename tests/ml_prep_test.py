import sqlite3
import pandas as pd

conn = sqlite3.connect('trading_agent.db')

# Let's see trade_feedback
tf = pd.read_sql_query("SELECT * FROM trade_feedback", conn)
print("Trade Feedback Columns:", tf.columns.tolist())
print(tf.head(2))

# Let's see transactions
tx = pd.read_sql_query("SELECT * FROM transactions", conn)
print("Transactions Columns:", tx.columns.tolist())

# Try to build a consolidated dataframe
# For each trade in trade_feedback, find the matching BUY and SELL in transactions to get holding duration
data = []
for _, row in tf.iterrows():
    ticker = row['ticker']
    # Approximate: find the latest SELL before or at the trade_feedback timestamp
    # Actually, it's easier to pair transactions
    
print("Total trades in feedback:", len(tf))

conn.close()
