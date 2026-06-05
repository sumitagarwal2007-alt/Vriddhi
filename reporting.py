import sqlite3
import pandas as pd

DB_NAME = "trading_agent.db"

def generate_report():
    try:
        conn = sqlite3.connect(DB_NAME)
    except Exception as e:
        print(f"Database error: {e}")
        return
        
    try:
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
    except Exception:
        print("No transactions found or database not initialized.")
        return
        
    if df.empty:
        print("No transactions found.")
        return
        
    buys = df[df['action'] == 'BUY'].copy()
    sells = df[df['action'] == 'SELL'].copy()
    
    # Naive merge assuming 1 BUY and 1 SELL per ticker for MVP tracking
    closed_trades = pd.merge(buys, sells, on='ticker', suffixes=('_buy', '_sell'))
    
    if closed_trades.empty:
        print("No closed trades yet to analyze performance.")
        print(f"Currently open positions: {len(buys)}")
        return
    
    # Calculate Realized Profit / Loss
    closed_trades['realized_pl'] = (closed_trades['execution_price_sell'] - closed_trades['execution_price_buy']) * closed_trades['share_qty_buy']
    closed_trades['win'] = closed_trades['realized_pl'] > 0
    
    total_trades = len(closed_trades)
    winning_trades = closed_trades['win'].sum()
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
    
    total_realized_pl = closed_trades['realized_pl'].sum()
    
    top_assets = closed_trades.groupby('ticker')['realized_pl'].sum().reset_index()
    top_assets = top_assets.sort_values(by='realized_pl', ascending=False)
    
    # Count total executed orders
    total_orders = len(df)
    
    print("\n" + "="*50)
    print(" 📊 VRIDDHI QUANT - PERFORMANCE REPORT")
    print("="*50)
    print(f"Total Executed Orders: {total_orders}")
    print(f"Total Closed Trades:   {total_trades}")
    print(f"Win Rate:              {win_rate:.2f}%")
    print(f"Total Realized P/L:    ${total_realized_pl:.2f}")
    print("\n🏆 Top Performing Assets:")
    
    # Print markdown table
    print("| Ticker | Realized P/L ($) |")
    print("|--------|------------------|")
    for _, row in top_assets.iterrows():
        print(f"| {row['ticker']:<6} | {row['realized_pl']:>16.2f} |")
        
    print("\n" + "="*50)
    
    conn.close()

if __name__ == "__main__":
    generate_report()
