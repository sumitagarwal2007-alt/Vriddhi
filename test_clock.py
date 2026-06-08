import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
clock = trading_client.get_clock()
print("Is Open:", clock.is_open)
if not clock.is_open:
    print("Next Open:", clock.next_open.strftime('%m/%d %H:%M EST'))
