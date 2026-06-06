import asyncio
import os
import signal
import json
from datetime import datetime, timedelta
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

alpaca_stream = None
shutdown_event = None
GLOBAL_CIRCUIT_BREAKER_TRIPPED = False

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

import builtins
_orig_print = builtins.print
def _timestamped_print(*args, **kwargs):
    _orig_print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", *args, **kwargs)
builtins.print = _timestamped_print

async def handle_news(news):
    """The Prahari Loop: Callback for incoming news stream."""
    global GLOBAL_CIRCUIT_BREAKER_TRIPPED
    if GLOBAL_CIRCUIT_BREAKER_TRIPPED:
        return
        
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
        print(f"[Agent BIRBAL] Analysis: {analysis.sentiment.value} (Score: {analysis.significance_score}) - {analysis.reasoning}")
        
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
                if analysis.significance_score < 7:
                    print(f"[Prahari Loop] {ticker} ignored. Significance score {analysis.significance_score} is too low.")
                    continue
                    
                if md.get_spy_performance() < -0.01:
                    print(f"[Prahari Loop] {ticker} ignored. SPY Macro Trend is negative (Bleeding Market).")
                    continue
                
                current_price = md.get_live_price(ticker)
                if current_price <= 0:
                    continue
                
                stop_percent = md.calculate_dynamic_stop(ticker, current_price)
                
                target_time = (datetime.now() + timedelta(minutes=3)).isoformat()
                print(f"[Gateway YUKTI] {ticker} waitlisted at ${current_price}. Pending 3-min confirmation shield...")
                
                await db.add_to_waitlist(
                    ticker=ticker,
                    initial_price=current_price,
                    target_buy_time=target_time,
                    headline=headline,
                    stop_percent=stop_percent
                )
            
    except Exception as e:
        print(f"[Prahari Loop] Error processing news: {e}")

async def _run_stream(stream):
    """Run stream in thread to not block asyncio event loop."""
    await asyncio.to_thread(stream.run)

async def run_prahari_loop():
    """Runs the Alpaca News websocket stream."""
    global alpaca_stream
    if not API_KEY or API_KEY == "YOUR_ALPACA_KEY":
        print("[Prahari Loop] Alpaca keys missing. Simulating news stream logic offline...")
        # Keep loop alive for the sake of the system
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
        return
            
    try:
        alpaca_stream = NewsDataStream(API_KEY, SECRET_KEY)
        alpaca_stream.subscribe_news(handle_news, "*")
        print("[Prahari Loop] Connecting to Alpaca News Stream...")
        await _run_stream(alpaca_stream)
    except Exception as e:
        print(f"[Prahari Loop] Stream error: {e}")

async def run_waitlist_loop():
    """Checks waitlisted signals for price momentum confirmation after 3 minutes."""
    global GLOBAL_CIRCUIT_BREAKER_TRIPPED
    
    while not shutdown_event.is_set():
        try:
            waitlist = await db.get_waitlist()
            now = datetime.now()
            for w in waitlist:
                if GLOBAL_CIRCUIT_BREAKER_TRIPPED:
                    await db.remove_from_waitlist(w['ticker'])
                    continue
                    
                target_time = datetime.fromisoformat(w['target_buy_time'])
                if now >= target_time:
                    ticker = w['ticker']
                    initial_price = w['initial_price']
                    stop_percent = w['stop_percent']
                    
                    current_price = md.get_live_price(ticker)
                    if current_price > initial_price:
                        print(f"[Waitlist] Momentum Confirmed for {ticker}! ({initial_price} -> {current_price}). Executing Buy.")
                        
                        buy_budget = md.calculate_position_size(stop_percent)
                        qty = buy_budget / current_price
                        
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
                            print(f"[Waitlist] Mocking buy order for {qty:.4f} shares of {ticker}")
                            
                        if status != "FAILED":
                            timestamp = datetime.now().isoformat()
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
                                entry_time=timestamp,
                                profit_taken=0
                            )
                            notif.send_alert(
                                "🚨 Trade Executed (Buy)",
                                f"Waitlist momentum confirmed for **{ticker}**.\nBought {qty:.4f} shares at ${current_price:.2f}.",
                                0x00FF00
                            )
                    else:
                        print(f"[Waitlist] Fakeout detected for {ticker} ({initial_price} -> {current_price}). Dropping signal.")
                    
                    await db.remove_from_waitlist(ticker)
        except Exception as e:
            print(f"[Waitlist Loop] Error: {e}")
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass

async def run_chanakya_loop():
    """Agent CHANAKYA - Risk Manager. Evaluates active positions every 60 seconds."""
    global GLOBAL_CIRCUIT_BREAKER_TRIPPED
    
    while not shutdown_event.is_set():
        if GLOBAL_CIRCUIT_BREAKER_TRIPPED:
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
            continue
            
        try:
            # 1. Global Circuit Breaker Check
            if trading_client:
                account = trading_client.get_account()
                equity = float(account.equity)
                last_equity = float(account.last_equity)
                if last_equity > 0:
                    daily_change = (equity - last_equity) / last_equity
                    if daily_change <= -0.02:
                        print(f"[Agent CHANAKYA] 🚨 GLOBAL CIRCUIT BREAKER TRIPPED! Daily drop is {daily_change*100:.2f}%!")
                        GLOBAL_CIRCUIT_BREAKER_TRIPPED = True
                        
                        try:
                            trading_client.close_all_positions(cancel_orders=True)
                            print("[Agent CHANAKYA] Alpaca: ALL POSITIONS LIQUIDATED TO CASH.")
                        except Exception as e:
                            print(f"[Alpaca API] Close all positions error: {e}")
                            
                        await db.wipe_all_active_positions()
                        notif.send_alert(
                            "🚨 CIRCUIT BREAKER TRIPPED",
                            f"Portfolio dropped {daily_change*100:.2f}% today. All open positions forcefully liquidated to cash to protect the fund. System is in lockdown.",
                            color=0xFF0000
                        )
                        continue
                        
            # 1.5. Event Calendar Check (Pre-Event Liquidation)
            try:
                if os.path.exists("events.json"):
                    with open("events.json", "r") as f:
                        calendar = json.load(f)
                    now = datetime.now()
                    for ev in calendar.get("events", []):
                        ev_time = datetime.fromisoformat(ev["time"])
                        time_to_event = ev_time - now
                        if timedelta(0) <= time_to_event <= timedelta(minutes=15):
                            print(f"[Agent CHANAKYA] ⚠️ PRE-EVENT LIQUIDATION TRIGGERED for {ev['name']}")
                            if trading_client:
                                try:
                                    trading_client.close_all_positions(cancel_orders=True)
                                except Exception as e:
                                    print(f"[Alpaca API] Event Liquidation error: {e}")
                            await db.wipe_all_active_positions()
                            notif.send_alert("⚠️ Pre-Event Liquidation", f"Liquidated all positions ahead of: {ev['name']}. Pausing engine for 30 minutes.", color=0xFFA500)
                            
                            # Sleep for 30 minutes
                            await asyncio.sleep(1800)
                            break
            except Exception as e:
                print(f"[Agent CHANAKYA] Event calendar error: {e}")

            # 2. VIX Check (Fear Mode)
            vixy_change = md.get_vixy_change()
            is_fear_mode = vixy_change > 0.05
            if is_fear_mode:
                print(f"[Agent CHANAKYA] ⚠️ FEAR MODE ACTIVE. VIXY is spiking (+{vixy_change*100:.2f}%). Tightening all stops to 1.5%!")

            # 3. Macro Hedging
            spy_perf = md.get_spy_performance()
            positions = await db.get_active_positions()
            owns_sh = any(pos['ticker'] == 'SH' for pos in positions)
            
            if spy_perf <= -0.005 and not owns_sh:
                print("[Agent CHANAKYA] Macro bleeding detected (SPY <= -0.5%). Deploying SH Hedge!")
                sh_price = md.get_live_price("SH")
                if sh_price > 0:
                    qty = 500.0 / sh_price
                    order_id = "MOCK_HEDGE"
                    status = "FILLED"
                    if trading_client:
                        try:
                            req = MarketOrderRequest(symbol="SH", qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
                            order = trading_client.submit_order(order_data=req)
                            order_id = str(order.id)
                            status = order.status.value
                        except Exception as e:
                            print(f"[Alpaca API] SH Hedge error: {e}")
                            status = "FAILED"
                    if status != "FAILED":
                        ts = datetime.now().isoformat()
                        await db.log_transaction(ts, order_id, "SH", "BUY", qty, sh_price, "MARKET", status)
                        await db.add_active_position("SH", sh_price, qty, sh_price, 0.05, ts)
                        notif.send_alert("🛡️ Hedge Deployed", f"SPY dropped {spy_perf*100:.2f}%. Bought {qty:.2f} shares of SH to hedge.", 0x0000FF)
                        positions = await db.get_active_positions()
                        
            elif spy_perf > -0.005 and owns_sh:
                print("[Agent CHANAKYA] Macro recovered. Removing SH Hedge!")
                sh_pos = next(p for p in positions if p['ticker'] == 'SH')
                sh_qty = sh_pos['share_qty']
                sh_price = md.get_live_price("SH")
                order_id = "MOCK_HEDGE_SELL"
                status = "FILLED"
                if trading_client:
                    try:
                        req = MarketOrderRequest(symbol="SH", qty=sh_qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
                        order = trading_client.submit_order(order_data=req)
                        order_id = str(order.id)
                        status = order.status.value
                    except Exception as e:
                        print(f"[Alpaca API] SH Hedge Sell error: {e}")
                        status = "FAILED"
                if status != "FAILED":
                    ts = datetime.now().isoformat()
                    await db.log_transaction(ts, order_id, "SH", "SELL", sh_qty, sh_price, "MARKET", status)
                    await db.remove_active_position("SH")
                    notif.send_alert("🛡️ Hedge Removed", f"SPY recovered. Sold SH hedge.", 0x0000FF)
                    positions = await db.get_active_positions()

            # 4. Standard Position Tracking
            for pos in positions:
                ticker = pos['ticker']
                if ticker == 'SH':
                    continue # Managed by macro hedge logic above
                
                # Sleep 1.5 seconds per position to strictly respect Finnhub's 60 RPM free tier
                await asyncio.sleep(1.5)
                
                ticker = pos['ticker']
                highest_price = pos['highest_tracked_price']
                stop_percent = pos['dynamic_stop_percent']
                share_qty = pos['share_qty']
                purchase_price = pos['purchase_price']
                profit_taken = pos.get('profit_taken', 0)
                
                current_price = md.get_live_price(ticker)
                if current_price <= 0:
                    continue
                
                # Check Take-Profit (Scale Out)
                if not profit_taken and current_price >= purchase_price * 1.04:
                    print(f"[Agent CHANAKYA] {ticker} hit +4% profit target. Scaling out 50%!")
                    sell_qty = share_qty / 2.0
                    
                    order_id = "MOCK_SELL_HALF"
                    status = "FILLED"
                    if trading_client:
                        try:
                            req = MarketOrderRequest(
                                symbol=ticker,
                                qty=sell_qty,
                                side=OrderSide.SELL,
                                time_in_force=TimeInForce.DAY
                            )
                            order = trading_client.submit_order(order_data=req)
                            order_id = str(order.id)
                            status = order.status.value
                        except Exception as e:
                            print(f"[Alpaca API] Take-Profit Sell error: {e}")
                            status = "FAILED"
                    else:
                        print(f"[Agent CHANAKYA] Mocking take-profit sell order for {ticker}")
                    
                    if status != "FAILED":
                        timestamp = datetime.now().isoformat()
                        await db.log_transaction(
                            timestamp=timestamp,
                            alpaca_order_id=order_id,
                            ticker=ticker,
                            action="SELL",
                            share_qty=sell_qty,
                            execution_price=current_price,
                            order_type="MARKET",
                            status=status
                        )
                        await db.mark_profit_taken(ticker, sell_qty)
                        notif.send_alert(
                            "💰 Profit Taken (+4%)",
                            f"Agent Chanakya scaled out 50% of **{ticker}** at ${current_price:.2f}.",
                            0x00FF00
                        )
                    continue
                
                if current_price > highest_price:
                    await db.update_highest_price(ticker, current_price)
                    highest_price = current_price
                
                active_stop_percent = 0.015 if is_fear_mode else stop_percent
                stop_price = highest_price * (1 - active_stop_percent)
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
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass

async def shutdown_handler(sig):
    print(f"\n[Orchestrator] Received shutdown signal. Gracefully suspending engine...")
    shutdown_event.set()
    if alpaca_stream:
        try:
            alpaca_stream.stop_ws()
        except:
            pass
    notif.send_alert("⚠️ Engine Suspended", "Vriddhi Quant has been safely shut down for maintenance.", color=0xFFA500)

async def main():
    global shutdown_event
    shutdown_event = asyncio.Event()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown_handler(s)))
        
    print_banner()
    await db.init_db()
    md.load_sp500_universe()
    
    print("[Orchestrator] Starting loops...")
    await asyncio.gather(
        run_prahari_loop(),
        run_waitlist_loop(),
        run_chanakya_loop()
    )
    print("[Orchestrator] Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
