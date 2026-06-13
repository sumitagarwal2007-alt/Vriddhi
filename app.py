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
        df_tf = pd.read_sql_query("SELECT * FROM trade_feedback", conn)
        conn.close()
        
        trades, win_rate, pnl = 0, 0.0, 0.0
        
        if not df_tf.empty:
            trades = len(df_tf)
            win_rate = float((df_tf['pnl_pct'] > 0).sum() / trades * 100)
                
        if trading_client:
            try:
                acc = trading_client.get_account()
                port_val = float(acc.portfolio_value)
                
                # Get unrealized P/L to find pure realized P/L
                positions = trading_client.get_all_positions()
                unrealized = sum(float(p.unrealized_pl) for p in positions)
                
                # Alpaca paper starts at 100,000.00
                pnl = (port_val - 100000.0) - unrealized
            except Exception as e:
                pass
        
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
                "reasoning": row['ai_reasoning'],
                "bear_thesis": row.get('bear_thesis', ''),
                "judge_verdict": row.get('judge_verdict', '')
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
                        direction = row.get('direction', 'LONG')
                        if direction == 'LONG':
                            stop_price = float(row['highest_tracked_price']) * (1 - float(row['dynamic_stop_percent']))
                        else:
                            stop_price = float(row['highest_tracked_price']) * (1 + float(row['dynamic_stop_percent']))
                    else:
                        direction = 'LONG'
                    
                    positions_list.append({
                        "ticker": ticker,
                        "qty": float(p.qty),
                        "cost_basis": float(p.cost_basis),
                        "unrealized_pl": float(p.unrealized_pl),
                        "unrealized_plpc": float(p.unrealized_plpc) * 100,
                        "stop_price": stop_price,
                        "current_price": float(p.current_price),
                        "direction": direction
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

@app.route('/api/feedback')
def api_feedback():
    from flask import request
    try:
        limit = request.args.get('limit', 15, type=int)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total trades count
        cursor.execute("SELECT COUNT(*) FROM trade_feedback")
        total_count = cursor.fetchone()[0]
        
        # Query trades with limit if limit > 0
        if limit > 0:
            cursor.execute("SELECT * FROM trade_feedback ORDER BY timestamp DESC LIMIT ?", (limit,))
        else:
            cursor.execute("SELECT * FROM trade_feedback ORDER BY timestamp DESC")
            
        rows = cursor.fetchall()
        conn.close()
        
        feedback_list = []
        for row in rows:
            # Check if columns exist in row keys (to handle legacy databases gracefully)
            keys = row.keys()
            tenali_critique = row['tenali_critique'] if 'tenali_critique' in keys else ""
            tenali_score = row['tenali_score'] if 'tenali_score' in keys else 0
            
            feedback_list.append({
                "ticker": row['ticker'],
                "headline": row['headline'],
                "sentiment": row['sentiment'],
                "significance_score": row['significance_score'],
                "reasoning": row['reasoning'],
                "buy_price": row['buy_price'],
                "sell_price": row['sell_price'],
                "pnl_pct": row['pnl_pct'] * 100 if row['pnl_pct'] is not None else 0.0,
                "timestamp": row['timestamp'],
                "tenali_critique": tenali_critique,
                "tenali_score": tenali_score
            })
        return jsonify({
            "status": "success", 
            "data": feedback_list,
            "total": total_count
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/lessons')
def api_lessons():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_lessons ORDER BY date DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                "status": "success",
                "date": row['date'],
                "lessons": row['lessons']
            })
        else:
            return jsonify({
                "status": "success",
                "date": "",
                "lessons": ""
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chart-data')
def api_chart_data():
    try:
        from datetime import datetime, time
        from zoneinfo import ZoneInfo
    except ImportError:
        import pytz as tz
        ZoneInfo = lambda x: tz.timezone(x)
        from datetime import datetime, time
    
    try:
        eastern = ZoneInfo('US/Eastern')
        now_est = datetime.now(eastern)
        
        # Get latest trade date from transactions to display historical days correctly on weekends
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DATE(timestamp) as tx_date FROM transactions ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            target_date_str = row['tx_date']
        else:
            target_date_str = now_est.strftime('%Y-%m-%d')
        conn.close()
        
        # Parse target date
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        open_dt = datetime.combine(target_date, time(9, 30), tzinfo=eastern)
        close_dt = datetime.combine(target_date, time(16, 0), tzinfo=eastern)
        
        start_ts = int(open_dt.timestamp())
        if target_date == now_est.date():
            end_ts = int(now_est.timestamp())
        else:
            end_ts = int(close_dt.timestamp())
            
        # 1. Fetch SPY candles from Finnhub
        token = os.getenv("FINNHUB_TOKEN")
        spy_candles = []
        if token and token != "YOUR_FINNHUB_KEY":
            url = f"https://finnhub.io/api/v1/stock/candle?symbol=SPY&resolution=5&from={start_ts}&to={end_ts}&token={token}"
            try:
                import requests
                resp = requests.get(url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('s') == 'ok':
                        closes = data['c']
                        times = data['t']
                        spy_candles = [{'time': t, 'close': c} for t, c in zip(times, closes)]
            except Exception as e:
                print(f"Error fetching SPY candles: {e}")
                
        if not spy_candles:
            # Generate mock candles if API is down or has no data
            import random
            random.seed(42)
            spy_price = 540.0
            current_ts = start_ts
            # Step every 10 mins
            while current_ts <= end_ts:
                spy_candles.append({'time': current_ts, 'close': spy_price})
                spy_price += random.uniform(-0.5, 0.6)
                current_ts += 600
                
        # 2. Get current portfolio value
        portfolio_equity = 100000.0
        if trading_client:
            try:
                acc = trading_client.get_account()
                portfolio_equity = float(acc.portfolio_value)
            except:
                pass
                
        # 3. Calculate closed trades profit/losses for target date
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
        conn.close()
        
        closed_trades = []
        total_realized = 0.0
        if not df.empty:
            df['date'] = pd.to_datetime(df['timestamp']).dt.date
            buys = df[df['action'] == 'BUY']
            sells = df[df['action'] == 'SELL']
            if not buys.empty and not sells.empty:
                merged = pd.merge(buys, sells, on='ticker', suffixes=('_buy', '_sell'))
                if not merged.empty:
                    merged['realized_pl'] = (merged['execution_price_sell'] - merged['execution_price_buy']) * merged['share_qty_buy']
                    merged['sell_date'] = pd.to_datetime(merged['timestamp_sell']).dt.date
                    merged_day = merged[merged['sell_date'] == target_date]
                    
                    for _, row in merged_day.iterrows():
                        sell_time_str = row['timestamp_sell']
                        try:
                            dt_parsed = pd.to_datetime(sell_time_str).tz_localize(None).tz_localize(eastern)
                            ts = int(dt_parsed.timestamp())
                        except:
                            ts = start_ts
                            
                        closed_trades.append({
                            'ticker': row['ticker'],
                            'time': ts,
                            'pnl_val': float(row['realized_pl'])
                        })
                        total_realized += float(row['realized_pl'])
                        
        # 4. Generate curves
        start_val = portfolio_equity - total_realized
        first_spy_price = spy_candles[0]['close'] if spy_candles else 540.0
        
        labels = []
        spy_data = []
        portfolio_data = []
        
        for c in spy_candles:
            candle_ts = c['time']
            dt_est = datetime.fromtimestamp(candle_ts, tz=eastern)
            labels.append(dt_est.strftime('%H:%M'))
            
            # SPY percentage change
            spy_change = ((c['close'] - first_spy_price) / first_spy_price) * 100
            spy_data.append(round(spy_change, 3))
            
            # Portfolio value up to this candle
            realized_so_far = sum(t['pnl_val'] for t in closed_trades if t['time'] <= candle_ts)
            port_val = start_val + realized_so_far
            port_change = ((port_val - start_val) / start_val) * 100
            portfolio_data.append(round(port_change, 3))
            
        # 5. Transactions for annotations
        annotations = []
        if not df.empty:
            df_day = df[df['date'] == target_date]
            for _, row in df_day.iterrows():
                try:
                    dt_parsed = pd.to_datetime(row['timestamp']).tz_localize(None).tz_localize(eastern)
                    ts = int(dt_parsed.timestamp())
                    closest_idx = 0
                    min_diff = float('inf')
                    for idx, c in enumerate(spy_candles):
                        diff = abs(c['time'] - ts)
                        if diff < min_diff:
                            min_diff = diff
                            closest_idx = idx
                except:
                    closest_idx = 0
                    
                annotations.append({
                    'ticker': row['ticker'],
                    'action': row['action'],
                    'price': float(row['execution_price']),
                    'time': dt_parsed.strftime('%H:%M') if 'dt_parsed' in locals() else '09:30',
                    'index': closest_idx
                })
                
        return jsonify({
            'status': 'success',
            'date': target_date_str,
            'labels': labels,
            'spy': spy_data,
            'portfolio': portfolio_data,
            'transactions': annotations
        })
    except Exception as chart_err:
        return jsonify({"status": "error", "message": str(chart_err)}), 500

if __name__ == '__main__':
    # Bind to 0.0.0.0 to allow access from other devices on the same WiFi
    app.run(host='0.0.0.0', port=8000, debug=True)
