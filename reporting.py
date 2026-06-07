import sqlite3
import pandas as pd

DB_NAME = "trading_agent.db"

def generate_report():
    try:
        conn = sqlite3.connect(DB_NAME)
    except Exception as e:
        err = f"Database error: {e}"
        print(err)
        return err
        
    try:
        df = pd.read_sql_query("SELECT * FROM transactions", conn)
    except Exception:
        err = "No transactions found or database not initialized."
        print(err)
        return err
        
    if df.empty:
        err = "No transactions found."
        print(err)
        return err
        
    buys = df[df['action'] == 'BUY'].copy()
    sells = df[df['action'] == 'SELL'].copy()
    
    # Naive merge assuming 1 BUY and 1 SELL per ticker for MVP tracking
    closed_trades = pd.merge(buys, sells, on='ticker', suffixes=('_buy', '_sell'))
    
    if closed_trades.empty:
        err = f"No closed trades yet to analyze performance.\nCurrently open positions: {len(buys)}"
        print(err)
        return err
    
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
    report_lines = []
    report_lines.append("\n" + "="*50)
    report_lines.append(" 📊 VRIDDHI QUANT - PERFORMANCE REPORT")
    report_lines.append("="*50)
    report_lines.append(f"Total Executed Orders: {total_orders}")
    report_lines.append(f"Total Closed Trades:   {total_trades}")
    report_lines.append(f"Win Rate:              {win_rate:.2f}%")
    report_lines.append(f"Total Realized P/L:    ${total_realized_pl:.2f}")
    report_lines.append("\n🏆 Top Performing Assets:")
    
    # Print markdown table
    report_lines.append("```text")
    report_lines.append("| Ticker | Realized P/L ($) |")
    report_lines.append("|--------|------------------|")
    for _, row in top_assets.iterrows():
        report_lines.append(f"| {row['ticker']:<6} | {row['realized_pl']:>16.2f} |")
    report_lines.append("```")
    report_lines.append("="*50)
    
    conn.close()
    
    full_report = "\n".join(report_lines)
    return full_report

if __name__ == "__main__":
    print(generate_report())
