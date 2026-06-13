import asyncio
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
import database as db

load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

async def main():
    if not API_KEY or API_KEY == "YOUR_ALPACA_KEY":
        print("Alpaca keys missing. Cannot check sync.")
        return

    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    
    try:
        alpaca_positions = trading_client.get_all_positions()
        alpaca_dict = {p.symbol: float(p.qty) for p in alpaca_positions}
    except Exception as e:
        print(f"Error fetching Alpaca positions: {e}")
        return

    local_positions = await db.get_active_positions()
    local_dict = {p['ticker']: float(p['share_qty']) for p in local_positions}

    print("--- SYNC REPORT ---")
    print("Alpaca Positions:", alpaca_dict)
    print("Local DB Positions:", local_dict)

    all_tickers = set(alpaca_dict.keys()).union(set(local_dict.keys()))
    
    in_sync = True
    for ticker in all_tickers:
        alpaca_qty = alpaca_dict.get(ticker, 0.0)
        local_qty = local_dict.get(ticker, 0.0)
        
        # small float difference check
        if abs(alpaca_qty - local_qty) > 0.0001:
            print(f"MISMATCH for {ticker}: Alpaca has {alpaca_qty}, Local DB has {local_qty}")
            in_sync = False
            
    if in_sync:
        print("\nDatabases are IN SYNC!")
    else:
        print("\nDatabases are OUT OF SYNC!")

if __name__ == "__main__":
    asyncio.run(main())
