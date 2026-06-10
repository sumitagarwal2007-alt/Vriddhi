import sqlite3
from datetime import datetime

DB_NAME = "trading_agent.db"

def bootstrap():
    print("[Bootstrap] Connecting to database...")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            headline TEXT,
            sentiment TEXT,
            significance_score INTEGER,
            reasoning TEXT,
            buy_price REAL,
            sell_price REAL,
            pnl_pct REAL,
            timestamp TEXT
        )
    ''')
    conn.commit()

    # Clear trade_feedback table first to avoid duplicate bootstrapping
    cursor.execute("DELETE FROM trade_feedback")
    conn.commit()

    # Retrieve transactions
    cursor.execute("SELECT * FROM transactions ORDER BY timestamp ASC")
    txs = [dict(r) for r in cursor.fetchall()]

    positions = {} # ticker -> list of buys
    trades = []

    for tx in txs:
        ticker = tx['ticker']
        action = tx['action']
        qty = tx['share_qty']
        price = tx['execution_price']
        ts = tx['timestamp']

        if action == 'BUY':
            if ticker not in positions:
                positions[ticker] = []
            positions[ticker].append({'qty': qty, 'price': price, 'timestamp': ts})
        elif action == 'SELL':
            # Match with buys
            buys = positions.get(ticker, [])
            qty_to_match = qty
            matched_buys = []
            total_buy_cost = 0.0

            while qty_to_match > 0 and buys:
                buy = buys[0]
                if buy['qty'] <= qty_to_match:
                    matched_buys.append(buy)
                    total_buy_cost += buy['qty'] * buy['price']
                    qty_to_match -= buy['qty']
                    buys.pop(0)
                else:
                    partial_buy = {'qty': qty_to_match, 'price': buy['price'], 'timestamp': buy['timestamp']}
                    matched_buys.append(partial_buy)
                    total_buy_cost += qty_to_match * buy['price']
                    buy['qty'] -= qty_to_match
                    qty_to_match = 0

            if matched_buys:
                avg_buy_price = total_buy_cost / qty
                pnl_pct = (price - avg_buy_price) / avg_buy_price
                first_buy_ts = matched_buys[0]['timestamp']
                
                # Retrieve matching signal
                cursor.execute(
                    "SELECT raw_headline, ai_sentiment, significance_score, ai_reasoning FROM signals_log "
                    "WHERE extracted_ticker = ? AND ai_sentiment = 'BULLISH' AND timestamp <= ? "
                    "ORDER BY timestamp DESC LIMIT 1",
                    (ticker, first_buy_ts)
                )
                sig = cursor.fetchone()
                if sig:
                    headline = sig['raw_headline']
                    sentiment = sig['ai_sentiment']
                    significance_score = sig['significance_score']
                    reasoning = sig['ai_reasoning']
                else:
                    headline = "Unknown headline"
                    sentiment = "BULLISH"
                    significance_score = 0
                    reasoning = "N/A"

                cursor.execute('''
                    INSERT INTO trade_feedback (ticker, headline, sentiment, significance_score, reasoning, buy_price, sell_price, pnl_pct, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (ticker, headline, sentiment, significance_score, reasoning, avg_buy_price, price, pnl_pct, ts))

    conn.commit()
    
    # Check count
    cursor.execute("SELECT COUNT(*) FROM trade_feedback")
    count = cursor.fetchone()[0]
    print(f"[Bootstrap] Successfully loaded {count} historical trades into trade_feedback.")
    
    conn.close()

if __name__ == '__main__':
    bootstrap()
