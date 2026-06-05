import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

from alpaca.data.live.news import NewsDataStream
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

import database as db
import ai_processor as ai
import market_data as md
import notifications as notif

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

trading_client = None
if API_KEY and SECRET_KEY and API_KEY != "YOUR_ALPACA_KEY":
    # Paper environment is enforced by paper=True
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

CASH_BUDGET = 500.0

def print_banner():
    banner = """
===================================================================
      VRIDDHI QUANT: ALGORITHMIC WEALTH COMPOUNDING CORE
===================================================================
[✓] Agent BIRBAL (Gemini Pro) - Active
[✓] Gateway YUKTI (S&P 500 & Finnhub) - Active
[✓] Agent CHANAKYA (Risk Engine) - Active
[✓] The Kosh Ledger (SQLite) - Active
===================================================================
    """
    print(banner)

async def handle_news(news):
    """The Prahari Loop: Callback for incoming news stream."""
    headline = news.headline
    # news.symbols might be a list
    timestamp = datetime.now().isoformat()
    
    print(f"[Prahari Loop] Received headline: {headline}")
    
    # Pre-Filter Shield: Check if any symbol in the news is in our universe
    has_eligible_symbol = False
    for sym in news.symbols:
        if md.is_eligible(sym):
            has_eligible_symbol = True
            break
            
    if not has_eligible_symbol:
        print(f"[Prahari Loop] Dropping irrelevant headline: {headline[:50]}...")
        return
        
    try:
        analysis = await ai.analyze_headline(headline)
        print(f"[Agent BIRBAL] Analysis: {analysis.sentiment.value} - {analysis.reasoning}")
        
        for ticker in analysis.tickers_found:
            is_eligible = md.is_eligible(ticker)
            
            await db.log_signal(
                timestamp=timestamp,
                raw_headline=headline,
                extracted_ticker=ticker,
                ai_sentiment=analysis.sentiment.value,
                ai_reasoning=analysis.reasoning,
                is_eligible=int(is_eligible)
            )
            
            if analysis.sentiment.value == "BULLISH" and is_eligible:
                current_price = md.get_live_price(ticker)
                if current_price <= 0:
                    continue
                
                stop_percent = md.calculate_dynamic_stop(ticker, current_price)
                
                print(f"[Gateway YUKTI] {ticker} is eligible. Price: ${current_price}, Stop: {stop_percent*100}%")
                
                qty = CASH_BUDGET / current_price
                
                order_id = "MOCK_ORDER"
                status = "FILLED"
                if trading_client:
                    try:
                        req = MarketOrderRequest(
                            symbol=ticker,
                            qty=qty,
                            side=OrderSide.BUY,
                            time_in_force=TimeInForce.DAY
                        )
                        order = trading_client.submit_order(order_data=req)
                        order_id = str(order.id)
                        status = order.status.value
                    except Exception as e:
                        print(f"[Alpaca API] Buy error: {e}")
                        status = "FAILED"
                else:
                    print("[Prahari Loop] Mocking buy order (API keys missing)")
                
                if status != "FAILED":
                    await db.log_transaction(
                        timestamp=timestamp,
                        alpaca_order_id=order_id,
                        ticker=ticker,
                        action="BUY",
                        share_qty=qty,
                        execution_price=current_price,
                        order_type="MARKET",
                        status=status
                    )
                    await db.add_active_position(
                        ticker=ticker,
                        purchase_price=current_price,
                        share_qty=qty,
                        highest_tracked_price=current_price,
                        dynamic_stop_percent=stop_percent,
                        entry_time=timestamp
                    )
                    notif.send_alert(
                        "🚨 Trade Executed (Buy)",
                        f"Agent Birbal detected bullish news for **{ticker}**.\nBought {qty:.4f} shares at ${current_price:.2f}.",
                        0x00FF00
                    )
            
    except Exception as e:
        print(f"[Prahari Loop] Error processing news: {e}")

async def _run_stream(stream):
    """Run stream in thread to not block asyncio event loop."""
    await asyncio.to_thread(stream.run)

async def run_prahari_loop():
    """Runs the Alpaca News websocket stream."""
    if not API_KEY or API_KEY == "YOUR_ALPACA_KEY":
        print("[Prahari Loop] Alpaca keys missing. Simulating news stream logic offline...")
        # Keep loop alive for the sake of the system
        while True:
            await asyncio.sleep(60)
            
    try:
        stream = NewsDataStream(API_KEY, SECRET_KEY)
        stream.subscribe_news(handle_news, "*")
        print("[Prahari Loop] Connecting to Alpaca News Stream...")
        await _run_stream(stream)
    except Exception as e:
        print(f"[Prahari Loop] Stream error: {e}")

async def run_chanakya_loop():
    """Agent CHANAKYA - Risk Manager. Evaluates active positions every 60 seconds."""
    while True:
        try:
            positions = await db.get_active_positions()
            for pos in positions:
                # Sleep 1.5 seconds per position to strictly respect Finnhub's 60 RPM free tier
                await asyncio.sleep(1.5)
                
                ticker = pos['ticker']
                highest_price = pos['highest_tracked_price']
                stop_percent = pos['dynamic_stop_percent']
                share_qty = pos['share_qty']
                
                current_price = md.get_live_price(ticker)
                if current_price <= 0:
                    continue
                
                if current_price > highest_price:
                    await db.update_highest_price(ticker, current_price)
                    highest_price = current_price
                
                stop_price = highest_price * (1 - stop_percent)
                if current_price <= stop_price:
                    print(f"[Agent CHANAKYA] {ticker} dropped below trailing stop ({stop_price:.2f}). Liquidating!")
                    
                    order_id = "MOCK_SELL_ORDER"
                    status = "FILLED"
                    if trading_client:
                        try:
                            req = MarketOrderRequest(
                                symbol=ticker,
                                qty=share_qty,
                                side=OrderSide.SELL,
                                time_in_force=TimeInForce.DAY
                            )
                            order = trading_client.submit_order(order_data=req)
                            order_id = str(order.id)
                            status = order.status.value
                        except Exception as e:
                            print(f"[Alpaca API] Sell error: {e}")
                            status = "FAILED"
                    else:
                        print(f"[Agent CHANAKYA] Mocking sell order for {ticker}")
                    
                    if status != "FAILED":
                        timestamp = datetime.now().isoformat()
                        await db.log_transaction(
                            timestamp=timestamp,
                            alpaca_order_id=order_id,
                            ticker=ticker,
                            action="SELL",
                            share_qty=share_qty,
                            execution_price=current_price,
                            order_type="MARKET",
                            status=status
                        )
                        await db.remove_active_position(ticker)
                        notif.send_alert(
                            "⚠️ Emergency Liquidation (Sell)",
                            f"Agent Chanakya triggered trailing stop for **{ticker}** at ${current_price:.2f}.",
                            0xFF0000
                        )
            
        except Exception as e:
            print(f"[Agent CHANAKYA] Error: {e}")
            
        await asyncio.sleep(60)

async def main():
    print_banner()
    await db.init_db()
    md.load_sp500_universe()
    
    print("[Orchestrator] Starting loops...")
    await asyncio.gather(
        run_prahari_loop(),
        run_chanakya_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())
