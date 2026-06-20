import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

acc = trading_client.get_account()
print(f"cash: {acc.cash}")
print(f"portfolio_value: {acc.portfolio_value}")
print(f"buying_power: {acc.buying_power}")
print(f"equity: {acc.equity}")
print(f"margin_multiplier: {acc.margin_multiplier}")
print(f"short_market_value: {acc.short_market_value}")
print(f"long_market_value: {acc.long_market_value}")
print(f"initial_margin: {acc.initial_margin}")
print(f"maintenance_margin: {acc.maintenance_margin}")
