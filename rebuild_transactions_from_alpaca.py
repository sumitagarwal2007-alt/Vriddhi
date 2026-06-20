import os
import asyncio
import aiosqlite
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
DB_NAME = "trading_agent.db"

async def rebuild_transactions():
    print("[*] Connecting to Alpaca...")
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    
    all_orders = []
    limit = 500
    until = None
    
    print("[*] Fetching historical orders from Alpaca...")
    while True:
        req = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=limit,
            until=until
        )
        orders = trading_client.get_orders(filter=req)
        
        if not orders:
            break
            
        all_orders.extend(orders)
        print(f"    Fetched {len(orders)} orders... (Total: {len(all_orders)})")
        
        if len(orders) < limit:
            break
            
        # Paginate
        until = orders[-1].submitted_at
        
    print(f"[*] Successfully fetched {len(all_orders)} total orders from Alpaca.")
    
    # Sort orders chronologically (oldest first)
    all_orders.sort(key=lambda o: o.submitted_at)
    
    print("[*] Rebuilding local database `transactions` table...")
    async with aiosqlite.connect(DB_NAME) as db:
        # Clear existing transactions
        await db.execute('DELETE FROM transactions')
        
        inserted_count = 0
        for order in all_orders:
            # We only care about orders that actually filled to some degree or were logged
            # But to match exact history, we can log all of them
            timestamp = order.filled_at.isoformat() if order.filled_at else order.submitted_at.isoformat()
            order_id = str(order.id)
            ticker = order.symbol
            
            # Map side to action
            action = "BUY" if order.side.value == "buy" else "SELL"
            
            share_qty = float(order.filled_qty) if order.filled_qty else 0.0
            if share_qty == 0 and order.qty:
                share_qty = float(order.qty) # Fallback to requested qty if not filled
                
            execution_price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
            order_type = order.order_type.value.upper() if order.order_type else "MARKET"
            status = order.status.value
            
            # Skip logging failed/canceled orders that have 0 filled quantity
            if status in ('canceled', 'rejected', 'expired', 'replaced', 'pending_cancel') and float(order.filled_qty or 0) == 0:
                continue
                
            await db.execute('''
                INSERT INTO transactions (timestamp, alpaca_order_id, ticker, action, share_qty, execution_price, order_type, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, order_id, ticker, action, share_qty, execution_price, order_type, status))
            inserted_count += 1
            
        await db.commit()
        print(f"[*] Rebuild complete! Inserted {inserted_count} historical transactions into the database.")

if __name__ == "__main__":
    asyncio.run(rebuild_transactions())
