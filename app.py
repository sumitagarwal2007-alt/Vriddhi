import os
import sqlite3
import pandas as pd
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

trading_client = None
if API_KEY and SECRET_KEY and API_KEY != "YOUR_ALPACA_KEY":
    try:
        trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    except:
        pass

DB_NAME = "trading_agent.db"

app = Flask(__name__)
CORS(app)

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def api_stats():
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
        conn.close()
        
        trades, win_rate, pnl = 0, 0.0, 0.0
        
        if not df.empty:
            buys = df[df['action'] == 'BUY']
            sells = df[df['action'] == 'SELL']
            closed_trades = pd.merge(buys, sells, on='ticker', suffixes=('_buy', '_sell'))
            
            if not closed_trades.empty:
                closed_trades['realized_pl'] = (closed_trades['execution_price_sell'] - closed_trades['execution_price_buy']) * closed_trades['share_qty_buy']
                pnl = float(closed_trades['realized_pl'].sum())
                win_rate = float((closed_trades['realized_pl'] > 0).sum() / len(closed_trades) * 100)
                trades = len(closed_trades)
        
        market_status = "UNKNOWN"
        next_open = ""
        is_open = False
        if trading_client:
            try:
                clock = trading_client.get_clock()
                is_open = clock.is_open
                if is_open:
                    market_status = "OPEN"
                else:
                    next_open = clock.next_open.strftime('%m/%d %H:%M EST')
                    market_status = "CLOSED"
            except Exception:
                pass

        return jsonify({
            "status": "success",
            "trades": trades,
            "win_rate": win_rate,
            "pnl": pnl,
            "market_status": market_status,
            "next_open": next_open,
            "is_open": is_open
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/kosh')
def api_kosh():
    if not trading_client:
        return jsonify({"status": "error", "message": "Alpaca API not configured."}), 500
    try:
        acc = trading_client.get_account()
        return jsonify({
            "status": "success",
            "cash": float(acc.cash),
            "portfolio_value": float(acc.portfolio_value),
            "buying_power": float(acc.buying_power)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/news')
def api_news():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals_log ORDER BY id DESC LIMIT 15")
        rows = cursor.fetchall()
        conn.close()
        
        news_list = []
        for row in rows:
            news_list.append({
                "timestamp": row['timestamp'],
                "ticker": row['extracted_ticker'],
                "sentiment": row['ai_sentiment'],
                "headline": row['raw_headline'],
                "reasoning": row['ai_reasoning']
            })
        return jsonify({"status": "success", "data": news_list})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/positions')
def api_positions():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM active_positions")
        db_rows = cursor.fetchall()
        db_positions = {row['ticker']: dict(row) for row in db_rows}
        
        cursor.execute("SELECT * FROM waitlist_positions")
        waitlist_rows = cursor.fetchall()
        waitlist_positions = [dict(row) for row in waitlist_rows]
        
        conn.close()
        
        positions_list = []
        if trading_client:
            try:
                positions = trading_client.get_all_positions()
                for p in positions:
                    ticker = p.symbol
                    stop_price = None
                    if ticker in db_positions:
                        row = db_positions[ticker]
                        stop_price = float(row['highest_tracked_price']) * (1 - float(row['dynamic_stop_percent']))
                    
                    positions_list.append({
                        "ticker": ticker,
                        "qty": float(p.qty),
                        "cost_basis": float(p.cost_basis),
                        "unrealized_pl": float(p.unrealized_pl),
                        "unrealized_plpc": float(p.unrealized_plpc) * 100,
                        "stop_price": stop_price,
                        "current_price": float(p.current_price)
                    })
            except Exception as e:
                print(f"Error fetching positions from Alpaca: {e}")
        
        return jsonify({
            "status": "success", 
            "active": positions_list,
            "waitlist": waitlist_positions
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Bind to 0.0.0.0 to allow access from other devices on the same WiFi
    app.run(host='0.0.0.0', port=5000, debug=True)
