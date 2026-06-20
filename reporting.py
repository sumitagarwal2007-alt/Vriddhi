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
        
    # Sort values to process ledger linearly
    df = df.sort_values(by='timestamp')
    
    open_positions_calc = {}
    asset_pnl = {}
    total_realized_pl = 0.0
    
    for _, row in df.iterrows():
        ticker = row['ticker']
        action = row['action']
        qty = float(row['share_qty'])
        price = float(row['execution_price'])
        
        if ticker not in open_positions_calc:
            open_positions_calc[ticker] = {'qty': 0.0, 'total_cost': 0.0}
        if ticker not in asset_pnl:
            asset_pnl[ticker] = 0.0
            
        pos = open_positions_calc[ticker]
        if action == 'BUY':
            pos['qty'] += qty
            pos['total_cost'] += qty * price
        elif action == 'SELL':
            if pos['qty'] > 0:
                avg_cost = pos['total_cost'] / pos['qty']
                realized = (price - avg_cost) * qty
                total_realized_pl += realized
                asset_pnl[ticker] += realized
                
                pos['qty'] -= qty
                pos['total_cost'] -= avg_cost * qty
                if pos['qty'] <= 0.0001:
                    pos['qty'] = 0.0
                    pos['total_cost'] = 0.0

    try:
        df_tf = pd.read_sql_query("SELECT * FROM trade_feedback", conn)
        total_trades = len(df_tf)
        if total_trades > 0:
            win_rate = float((df_tf['pnl_pct'] > 0).sum() / total_trades * 100)
        else:
            win_rate = 0.0
    except Exception:
        total_trades = 0
        win_rate = 0.0

    # Top Assets
    top_assets_list = [{'ticker': t, 'realized_pl': p} for t, p in asset_pnl.items() if p != 0.0]
    top_assets = pd.DataFrame(top_assets_list)
    if not top_assets.empty:
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
