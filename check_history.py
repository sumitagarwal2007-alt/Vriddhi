import sqlite3
conn = sqlite3.connect("trading_agent.db")
c = conn.cursor()
c.execute("SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM trade_feedback")
print(c.fetchone())
conn.close()
