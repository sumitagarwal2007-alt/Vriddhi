import sqlite3
import pandas as pd
import time
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

DB_NAME = "trading_agent.db"

def get_performance_stats():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
        conn.close()
        
        if df.empty:
            return 0, 0.0, 0.0
            
        buys = df[df['action'] == 'BUY']
        sells = df[df['action'] == 'SELL']
        closed_trades = pd.merge(buys, sells, on='ticker', suffixes=('_buy', '_sell'))
        
        if closed_trades.empty:
            return 0, 0.0, 0.0
            
        closed_trades['realized_pl'] = (closed_trades['execution_price_sell'] - closed_trades['execution_price_buy']) * closed_trades['share_qty_buy']
        total_realized_pl = closed_trades['realized_pl'].sum()
        win_rate = (closed_trades['realized_pl'] > 0).sum() / len(closed_trades) * 100
        
        return len(closed_trades), win_rate, total_realized_pl
    except Exception:
        return 0, 0.0, 0.0

def generate_header():
    trades, win_rate, pnl = get_performance_stats()
    color = "green" if pnl >= 0 else "red"
    header_text = Text(f"VRIDDHI QUANT GOD'S EYE | Total Realized P/L: ${pnl:.2f} | Win Rate: {win_rate:.1f}% | Closed Trades: {trades}", style=f"bold {color}")
    return Panel(Align.center(header_text), style="blue")

def generate_news_table():
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Time", style="dim", width=10)
    table.add_column("Ticker", width=8)
    table.add_column("Sentiment", width=10)
    table.add_column("Headline", width=45)
    table.add_column("Reasoning", width=45)

    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM signals_log ORDER BY id DESC LIMIT 8", conn)
        conn.close()
        
        if not df.empty:
            for _, row in df.iterrows():
                time_str = row['timestamp'].split('T')[1][:8] if 'T' in row['timestamp'] else str(row['timestamp'])
                color = "green" if row['ai_sentiment'] == "BULLISH" else ("red" if row['ai_sentiment'] == "BEARISH" else "white")
                headline = row['raw_headline'][:42] + "..." if len(row['raw_headline']) > 45 else row['raw_headline']
                reasoning = row['ai_reasoning'][:42] + "..." if len(row['ai_reasoning']) > 45 else row['ai_reasoning']
                
                table.add_row(time_str, str(row['extracted_ticker']), f"[{color}]{row['ai_sentiment']}[/{color}]", headline, reasoning)
    except Exception:
        pass
        
    return Panel(table, title="📰 Latest Intelligence (Agent BIRBAL)", border_style="cyan")

def generate_positions_table():
    table = Table(show_header=True, header_style="bold yellow", expand=True)
    table.add_column("Ticker")
    table.add_column("Entry $")
    table.add_column("High $")
    table.add_column("Stop %")
    table.add_column("Stop $")

    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM active_positions", conn)
        conn.close()
        
        if not df.empty:
            for _, row in df.iterrows():
                stop_price = row['highest_tracked_price'] * (1 - row['dynamic_stop_percent'])
                table.add_row(
                    str(row['ticker']), 
                    f"${row['purchase_price']:.2f}", 
                    f"${row['highest_tracked_price']:.2f}",
                    f"{row['dynamic_stop_percent']*100:.1f}%",
                    f"[red]${stop_price:.2f}[/red]"
                )
    except Exception:
        pass
        
    return Panel(table, title="⚔️ The Battlefield (Agent CHANAKYA)", border_style="green")

def make_layout():
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main")
    )
    layout["main"].split_row(
        Layout(name="news", ratio=6),
        Layout(name="positions", ratio=4)
    )
    
    layout["header"].update(generate_header())
    layout["news"].update(generate_news_table())
    layout["positions"].update(generate_positions_table())
    
    return layout

if __name__ == "__main__":
    print("Initializing God's Eye view...")
    try:
        with Live(make_layout(), refresh_per_second=1, screen=True) as live:
            while True:
                time.sleep(2)
                live.update(make_layout())
    except KeyboardInterrupt:
        print("Dashboard closed.")
