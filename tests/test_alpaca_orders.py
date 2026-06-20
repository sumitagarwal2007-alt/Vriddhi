import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

try:
    req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100)
    orders = trading_client.get_orders(filter=req)
    print(f"Fetched {len(orders)} orders.")
    if orders:
        o = orders[0]
        print(f"Sample order: {o.symbol} {o.side} {o.filled_qty} @ {o.filled_avg_price} status={o.status}")
except Exception as e:
    print(f"Error: {e}")
