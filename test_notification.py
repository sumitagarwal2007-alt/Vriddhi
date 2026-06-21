import notifications as notif
import time

def run_tests():
    print("Sending Buy Alert...")
    notif.send_alert(
        title="🟢 Institutional Buy Executed",
        description="ML Gatekeeper approved and VWAP limit order filled successfully.",
        color=0x00FFCC,
        fields={
            "Ticker": "NVDA",
            "Action": "LONG",
            "Filled Qty": "4.6042",
            "Execution Price": "$210.01",
            "ML Win Prob": "82.4%",
            "ATR Stop Loss": "$197.40 (6.0%)"
        }
    )
    time.sleep(2)
    
    print("Sending Sell Alert...")
    notif.send_alert(
        title="🔴 Stop Loss Triggered",
        description="Trailing ATR Stop Loss hit. Position liquidated to protect capital.",
        color=0xFF3366,
        fields={
            "Ticker": "AAPL",
            "Action": "SELL TO CLOSE",
            "Filled Qty": "3.2580",
            "Exit Price": "$295.10",
            "Realized P/L": "-$6.94",
            "Reason": "ATR Volatility Breach"
        }
    )
    time.sleep(2)
    
    print("Sending EOD Summary...")
    notif.send_alert(
        title="📊 End of Day Summary",
        description="Market is now closed. Nightly maintenance routines starting.",
        color=0x3B82F6,
        fields={
            "Total Trades": "2",
            "Daily Realized P/L": "+$42.15",
            "Current Portfolio": "$100,042.15",
            "Win Rate": "50.0%",
            "Waitlist Size": "4"
        }
    )

if __name__ == "__main__":
    run_tests()
