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
import self_heal
import traceback
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

def is_market_open() -> bool:
    """Returns True if the US Stock Market is currently open."""
    if trading_client:
        try:
            return trading_client.get_clock().is_open
        except Exception:
            return True
    return True

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
        print(f"[Agent BIRBAL] Headline processed. Found {len(analysis.analyses)} ticker(s) to evaluate.")
        
        for ticker_analysis in analysis.analyses:
            ticker = ticker_analysis.ticker
            is_eligible = md.is_eligible(ticker)
            sentiment_val = ticker_analysis.sentiment.value
            
            print(f"  -> {ticker}: {sentiment_val} (Score: {ticker_analysis.significance_score})")
            
            if not is_eligible or sentiment_val not in ["BULLISH", "BEARISH"]:
                continue
                
            print(f"[Prahari Loop] Invoking Agent BHISHMA for a contrarian attack on {ticker}...")
            try:
                bhishma_analysis = await ai.analyze_headline_bhishma(headline, ticker, sentiment_val, ticker_analysis.reasoning)
                print(f"[Agent BHISHMA] Contrarian Score: {bhishma_analysis.significance_score}")
                bear_thesis = bhishma_analysis.contrarian_thesis
            except Exception as e:
                print(f"[Prahari Loop] Agent BHISHMA error: {e}")
                bear_thesis = "Bhishma offline."
                
            print(f"[Prahari Loop] Invoking Agent VIKRAMADITYA (Judge) to resolve the debate...")
            try:
                vikram_analysis = await ai.analyze_headline_vikramaditya(headline, ticker, sentiment_val, ticker_analysis.reasoning, bear_thesis)
                print(f"[Agent VIKRAMADITYA] Verdict: Approved={vikram_analysis.approved} | {vikram_analysis.verdict}")
                approved = vikram_analysis.approved
                verdict = vikram_analysis.verdict
            except Exception as e:
                print(f"[Prahari Loop] Agent VIKRAMADITYA error: {e}")
                approved = True
                verdict = "Judge offline - auto-approved"
                
            if not approved:
                print(f"[Prahari Loop] {ticker} {sentiment_val} thesis REJECTED by Judge. Reason: {verdict}")
                # We could log this to signals_log, but for brevity we'll skip DB logging of rejections for now
                continue
                
            if ticker_analysis.significance_score < 7:
                print(f"[Prahari Loop] {ticker} ignored. Significance score {ticker_analysis.significance_score} is too low.")
                continue
                
            # Macro trend check
            if sentiment_val == "BULLISH" and md.get_spy_performance() < -0.01:
                print(f"[Prahari Loop] {ticker} BULLISH ignored. SPY Macro Trend is negative (Bleeding Market).")
                continue
            if sentiment_val == "BEARISH" and md.get_spy_performance() > 0.01:
                print(f"[Prahari Loop] {ticker} BEARISH ignored. SPY Macro Trend is overwhelmingly positive.")
                continue
            
            current_price = md.get_live_price(ticker)
            if current_price <= 0:
                continue
            
            stop_percent = md.calculate_dynamic_stop(ticker, current_price)
            
            if is_market_open():
                target_time = (datetime.now() + timedelta(minutes=3)).isoformat()
                is_overnight = 0
                print(f"[Gateway YUKTI] {ticker} waitlisted at ${current_price} as {sentiment_val}. Pending 3-min confirmation shield...")
            else:
                if trading_client:
                    try:
                        clock = trading_client.get_clock()
                        target_dt = clock.next_open - timedelta(minutes=30)
                        target_time = target_dt.isoformat()
                    except:
                        target_time = (datetime.now() + timedelta(hours=12)).isoformat()
                else:
                    target_time = (datetime.now() + timedelta(hours=12)).isoformat()
                is_overnight = 1
                print(f"[Gateway YUKTI] Night Watch Active. {ticker} queued for Pre-Market Re-Evaluation at {target_time}.")
            
            direction = "LONG" if sentiment_val == "BULLISH" else "SHORT"
            
            await db.add_to_waitlist(
                ticker=ticker,
                initial_price=current_price,
                target_buy_time=target_time,
                headline=headline,
                stop_percent=stop_percent,
                is_overnight=is_overnight,
                significance_score=ticker_analysis.significance_score
            )
            
            # Need to update waitlist query to support direction
            # We'll update add_to_waitlist locally via db.py next
            
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
            
    print("[Prahari Loop] Waiting 15 seconds for Alpaca servers to purge old ghost connections...")
    await asyncio.sleep(15)
    
    while not shutdown_event.is_set():
        try:
            alpaca_stream = NewsDataStream(API_KEY, SECRET_KEY)
            alpaca_stream.subscribe_news(handle_news, "*")
            print("[Prahari Loop] Connecting to Alpaca News Stream...")
            await _run_stream(alpaca_stream)
        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"[Prahari Loop] Stream error: {e}")
            ai_fix = await self_heal.diagnose_crash("Prahari Loop", e, tb_str)
            if "Suppressed" not in ai_fix:
                notif.send_alert("🚨 Engine Crash (Prahari Loop)", f"**Error**: {e}\n\n**AI Diagnosis/Patch**:\n```python\n{ai_fix[:1500]}\n```", 0xFF0000)
            print("[Prahari Loop] Waiting 10 seconds before auto-reconnect...")
            await asyncio.sleep(10)

async def run_waitlist_loop():
    """Checks waitlisted signals for technical confirmation (RSI/VWAP) and executes trades."""
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
                current_time = now.astimezone() if target_time.tzinfo is not None else now
                
                if current_time >= target_time:
                    ticker = w['ticker']
                    initial_price = w['initial_price']
                    stop_percent = w['stop_percent']
                    is_overnight = w.get('is_overnight', 0)
                    sig_score = w.get('significance_score', 7)
                    direction = w.get('direction', 'LONG')
                    
                    current_price = md.get_live_price(ticker)
                    if current_price <= 0:
                        continue
                        
                    # Fetch Technicals
                    rsi, vwap = md.get_rsi_vwap(ticker)
                    
                    if direction == 'LONG':
                        if rsi > 70:
                            print(f"[Waitlist] {ticker} RSI too high ({rsi:.1f}). Overbought. Dropping LONG.")
                            await db.remove_from_waitlist(ticker)
                            continue
                    else:
                        # SHORT
                        if rsi < 30:
                            print(f"[Waitlist] {ticker} RSI too low ({rsi:.1f}). Oversold. Dropping SHORT.")
                            await db.remove_from_waitlist(ticker)
                            continue
                            
                    print(f"[Waitlist] Technicals Confirmed for {ticker}! (Direction: {direction}, RSI: {rsi:.1f}, VWAP: {vwap:.2f}). Executing {direction}.")
                    
                    # V2 Kelly Criterion Sizing
                    portfolio_equity = 10000.0
                    if trading_client:
                        try:
                            account = trading_client.get_account()
                            portfolio_equity = float(account.equity)
                        except Exception as acc_err:
                            print(f"[Waitlist] Error fetching account equity: {acc_err}. Using baseline $10,000.")
                    
                    win_rate, win_ratio = await db.get_win_rate_and_ratio()
                    buy_budget = md.calculate_kelly_position_size(
                        portfolio_equity=portfolio_equity,
                        win_rate=win_rate,
                        win_loss_ratio=win_ratio,
                        direction=direction
                    )
                    qty = buy_budget / current_price
                    
                    order_id = "MOCK_ORDER"
                    status = "FILLED"
                    side = OrderSide.BUY if direction == 'LONG' else OrderSide.SELL
                    
                    if trading_client:
                        try:
                            req = MarketOrderRequest(
                                symbol=ticker,
                                qty=qty,
                                side=side,
                                time_in_force=TimeInForce.DAY
                            )
                            order = trading_client.submit_order(order_data=req)
                            order_id = str(order.id)
                            status = order.status.value
                            
                            await asyncio.sleep(2.0)
                            try:
                                updated_order = trading_client.get_order_by_id(order_id)
                                status = updated_order.status.value
                                if updated_order.filled_avg_price:
                                    current_price = float(updated_order.filled_avg_price)
                                if updated_order.filled_qty:
                                    qty = float(updated_order.filled_qty)
                            except:
                                pass
                        except Exception as e:
                            print(f"[Alpaca API] {direction} error: {e}")
                            status = "FAILED"
                    else:
                        print(f"[Waitlist] Mocking {direction} order for {qty:.4f} shares of {ticker}")
                        
                    if status != "FAILED":
                        timestamp = datetime.now().isoformat()
                        await db.log_transaction(
                            timestamp=timestamp,
                            alpaca_order_id=order_id,
                            ticker=ticker,
                            action="SELL_SHORT" if direction == "SHORT" else "BUY",
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
                            profit_taken=0,
                            significance_score=sig_score,
                            direction=direction
                        )
                        notif.send_alert(
                            f"🚨 Trade Executed ({direction})",
                            f"Technicals confirmed for **{ticker}**.\\n{direction} {qty:.4f} shares at ${current_price:.2f}.",
                            0x00FF00 if direction == "LONG" else 0xFF0000
                        )
                    
                    await db.remove_from_waitlist(ticker)
        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"[Waitlist Loop] Fatal Error: {e}")
            ai_fix = await self_heal.diagnose_crash("Waitlist Loop", e, tb_str)
            if "Suppressed" not in ai_fix:
                notif.send_alert("🚨 Engine Crash (Waitlist Loop)", f"**Error**: {e}\n\n**AI Diagnosis/Patch**:\n```python\n{ai_fix[:1500]}\n```", 0xFF0000)
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass


async def run_chanakya_loop():
    """Agent CHANAKYA - Risk Manager. Evaluates active positions every 60 seconds."""
    global GLOBAL_CIRCUIT_BREAKER_TRIPPED
    
    while not shutdown_event.is_set():
        if not is_market_open():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
            continue
            
        if GLOBAL_CIRCUIT_BREAKER_TRIPPED:
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
            continue
            
        try:
            positions = await db.get_active_positions()
            if not positions:
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass
                continue
                
            spy_perf = md.get_spy_performance()
            owns_sh = any(p['ticker'] == 'SH' for p in positions)
            
            for pos in positions:
                ticker = pos['ticker']
                if ticker == 'SH':
                    continue
                
                await asyncio.sleep(1.5)
                
                try:
                    highest_price = pos['highest_tracked_price']
                    stop_percent = pos['dynamic_stop_percent']
                    share_qty = pos['share_qty']
                    purchase_price = pos['purchase_price']
                    profit_taken = pos.get('profit_taken', 0)
                    direction = pos.get('direction', 'LONG')
                    
                    current_price = md.get_live_price(ticker)
                    if current_price <= 0:
                        continue
                    
                    sig_score = pos.get('significance_score', 7)
                    tp_threshold = 1.06 if sig_score >= 9 else 1.035
                    
                    # Take Profit
                    hit_tp = False
                    if direction == 'LONG' and current_price >= purchase_price * tp_threshold:
                        hit_tp = True
                    elif direction == 'SHORT' and current_price <= purchase_price * (2 - tp_threshold):
                        hit_tp = True
                        
                    if not profit_taken and hit_tp:
                        tp_pct_str = f"{(tp_threshold-1)*100:.1f}%"
                        print(f"[Agent CHANAKYA] {ticker} hit {tp_pct_str} profit target. Scaling out 50%!")
                        sell_qty = share_qty / 2.0
                        
                        order_id = "MOCK_SELL_HALF"
                        status = "FILLED"
                        side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY
                        if trading_client:
                            try:
                                req = MarketOrderRequest(
                                    symbol=ticker,
                                    qty=sell_qty,
                                    side=side,
                                    time_in_force=TimeInForce.DAY
                                )
                                order = trading_client.submit_order(order_data=req)
                                order_id = str(order.id)
                                status = order.status.value
                            except Exception as e:
                                print(f"[Alpaca API] Take-Profit Sell error: {e}")
                                status = "FAILED"
                        
                        if status != "FAILED":
                            timestamp = datetime.now().isoformat()
                            await db.log_transaction(
                                timestamp=timestamp,
                                alpaca_order_id=order_id,
                                ticker=ticker,
                                action="SELL" if direction == "LONG" else "COVER",
                                share_qty=sell_qty,
                                execution_price=current_price,
                                order_type="MARKET",
                                status=status
                            )
                            await db.log_trade_feedback(ticker, current_price, timestamp)
                            await db.mark_profit_taken(ticker, sell_qty)
                        continue
                    
                    # Trailing Stop Update
                    if direction == 'LONG':
                        if current_price > highest_price:
                            await db.update_highest_price(ticker, current_price)
                            highest_price = current_price
                        stop_price = highest_price * (1 - stop_percent)
                        triggered = current_price <= stop_price
                    else: # SHORT
                        # For short, "highest_price" in DB actually means "lowest_price" tracked
                        # We initialize highest_tracked_price = purchase_price.
                        if current_price < highest_price:
                            await db.update_highest_price(ticker, current_price)
                            highest_price = current_price
                        stop_price = highest_price * (1 + stop_percent)
                        triggered = current_price >= stop_price
                        
                    if triggered:
                        print(f"[Agent CHANAKYA] {ticker} {direction} trailing stop hit ({stop_price:.2f}). Liquidating!")
                        
                        order_id = "MOCK_SELL_ORDER"
                        status = "FILLED"
                        if trading_client:
                            try:
                                order = trading_client.close_position(
                                    symbol_or_asset_id=ticker,
                                    cancel_orders=True
                                )
                                order_id = str(order.id)
                                status = order.status.value
                            except Exception as e:
                                print(f"[Alpaca API] Liquidation error: {e}")
                                status = "FAILED"
                        
                        if status != "FAILED":
                            timestamp = datetime.now().isoformat()
                            await db.log_transaction(
                                timestamp=timestamp,
                                alpaca_order_id=order_id,
                                ticker=ticker,
                                action="SELL" if direction == "LONG" else "COVER",
                                share_qty=share_qty,
                                execution_price=current_price,
                                order_type="MARKET",
                                status=status
                            )
                            await db.log_trade_feedback(ticker, current_price, timestamp)
                            await db.remove_active_position(ticker)
                            
                except Exception as pos_err:
                    print(f"[Agent CHANAKYA] Error tracking position {ticker}: {pos_err}")
            
        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"[Agent CHANAKYA] Fatal Error: {e}")
            ai_fix = await self_heal.diagnose_crash("Chanakya Loop", e, tb_str)
            if "Suppressed" not in ai_fix:
                notif.send_alert("🚨 Engine Crash (Chanakya Loop)", f"**Error**: {e}\n\n**AI Diagnosis/Patch**:\n```python\n{ai_fix[:1500]}\n```", 0xFF0000)
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass

            continue
            
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
                            
                        try:
                            positions = await db.get_active_positions()
                            for pos in positions:
                                ticker = pos['ticker']
                                if ticker == 'SH':
                                    continue
                                current_price = md.get_live_price(ticker)
                                if current_price > 0:
                                    await db.log_trade_feedback(ticker, current_price, datetime.now().isoformat())
                        except Exception as feedback_err:
                            print(f"[Agent CHANAKYA] Error logging circuit breaker feedback: {feedback_err}")
                            
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
                            try:
                                positions = await db.get_active_positions()
                                for pos in positions:
                                    ticker = pos['ticker']
                                    if ticker == 'SH':
                                        continue
                                    current_price = md.get_live_price(ticker)
                                    if current_price > 0:
                                        await db.log_trade_feedback(ticker, current_price, datetime.now().isoformat())
                            except Exception as feedback_err:
                                print(f"[Agent CHANAKYA] Error logging event liquidation feedback: {feedback_err}")
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

            # 3. True Position Reconciliation (Alpaca Override)
            if trading_client:
                alpaca_positions = trading_client.get_all_positions()
                alpaca_dict = {p.symbol: float(p.qty) for p in alpaca_positions}
                local_positions = await db.get_active_positions()
                local_dict = {p['ticker']: p for p in local_positions}
                
                positions = []
                for ticker, qty in alpaca_dict.items():
                    if ticker not in local_dict:
                        if ticker != 'SH':
                            current_price = md.get_live_price(ticker)
                            stop_percent = md.calculate_dynamic_stop(ticker, current_price) if current_price > 0 else 0.025
                            await db.add_active_position(ticker, current_price, qty, current_price, stop_percent, datetime.now().isoformat())
                            local_pos = {
                                'ticker': ticker, 'purchase_price': current_price, 'share_qty': qty, 
                                'highest_tracked_price': current_price, 'dynamic_stop_percent': stop_percent,
                                'profit_taken': 0, 'significance_score': 7
                            }
                            positions.append(local_pos)
                        else:
                            positions.append({'ticker': 'SH', 'share_qty': qty})
                    else:
                        local_pos = local_dict[ticker]
                        local_pos['share_qty'] = qty # Force Alpaca truth
                        positions.append(local_pos)
            else:
                positions = await db.get_active_positions()

            # 3.5. Macro Hedging
            spy_perf = md.get_spy_performance()
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
                
                try:
                    highest_price = pos['highest_tracked_price']
                    stop_percent = pos['dynamic_stop_percent']
                    share_qty = pos['share_qty']
                    purchase_price = pos['purchase_price']
                    profit_taken = pos.get('profit_taken', 0)
                    
                    current_price = md.get_live_price(ticker)
                    if current_price <= 0:
                        continue
                    
                    # Check Take-Profit (Scale Out) - V3 Dynamic Take Profit
                    sig_score = pos.get('significance_score', 7)
                    tp_threshold = 1.06 if sig_score >= 9 else 1.035
                    
                    if not profit_taken and current_price >= purchase_price * tp_threshold:
                        tp_pct_str = f"+{(tp_threshold-1)*100:.1f}%"
                        print(f"[Agent CHANAKYA] {ticker} hit {tp_pct_str} profit target. Scaling out 50%!")
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
                            await db.log_trade_feedback(ticker, current_price, timestamp)
                            await db.mark_profit_taken(ticker, sell_qty)
                            notif.send_alert(
                                f"💰 Profit Taken ({tp_pct_str})",
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
                                order = trading_client.close_position(
                                    symbol_or_asset_id=ticker,
                                    cancel_orders=True
                                )
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
                            await db.log_trade_feedback(ticker, current_price, timestamp)
                            await db.remove_active_position(ticker)
                            notif.send_alert(
                                "⚠️ Emergency Liquidation (Sell)",
                                f"Agent Chanakya triggered trailing stop for **{ticker}** at ${current_price:.2f}.",
                                0xFF0000
                            )
                except Exception as pos_err:
                    print(f"[Agent CHANAKYA] Error tracking position {ticker}: {pos_err}")
            
        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"[Agent CHANAKYA] Fatal Error: {e}")
            ai_fix = await self_heal.diagnose_crash("Chanakya Loop", e, tb_str)
            if "Suppressed" not in ai_fix:
                notif.send_alert("🚨 Engine Crash (Chanakya Loop)", f"**Error**: {e}\n\n**AI Diagnosis/Patch**:\n```python\n{ai_fix[:1500]}\n```", 0xFF0000)
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass

async def run_premarket_reflection_loop():
    """Agent GURU - Pre-Market Self-Learning Reflection loop.
    Automatically identifies and reflects on all completed trading days that lack reflection lessons.
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        import pytz as tz
        ZoneInfo = lambda x: tz.timezone(x)
        
    eastern = ZoneInfo('US/Eastern')
    
    while not shutdown_event.is_set():
        try:
            # 1. Get all unanalyzed trade dates
            unanalyzed_dates = await db.get_unanalyzed_trade_dates()
            now_est = datetime.now(eastern)
            current_date_str = now_est.strftime('%Y-%m-%d')
            
            for date_str in unanalyzed_dates:
                # Check if the date is fully completed
                is_completed = False
                if date_str < current_date_str:
                    is_completed = True
                elif date_str == current_date_str:
                    # Completed if current time is after 4:05 PM EST
                    if now_est.hour > 16 or (now_est.hour == 16 and now_est.minute >= 5):
                        is_completed = True
                        
                if is_completed:
                    print(f"[Agent GURU] No post-mortem lessons found for completed trade date {date_str}. Starting retrospective analysis...")
                    lessons_text = await ai.generate_daily_reflective_lessons(date_str)
                    print(f"[Agent GURU] Retrospective analysis complete for {date_str}!")
                    notif.send_alert(
                        "🧠 Daily Self-Learning Post-Mortem",
                        f"Agent GURU completed retrospective analysis on trades from **{date_str}**:\n\n{lessons_text}",
                        0x8A2BE2
                    )
                    # Brief pause between reflections to prevent API rate limits if catching up on multiple days
                    await asyncio.sleep(5)
        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"[Agent GURU] Fatal Error: {e}")
            ai_fix = await self_heal.diagnose_crash("Guru Loop", e, tb_str)
            if "Suppressed" not in ai_fix:
                notif.send_alert("🚨 Engine Crash (Guru Loop)", f"**Error**: {e}\n\n**AI Diagnosis/Patch**:\n```python\n{ai_fix[:1500]}\n```", 0xFF0000)
            
        # Check every 15 minutes
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=900)
        except asyncio.TimeoutError:
            pass



async def run_eod_report_loop():
    """Agent SURYA - End of Day Reporting. Sends a Discord summary at 4:05 PM EST."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        import pytz as tz
        ZoneInfo = lambda x: tz.timezone(x)
        
    eastern = ZoneInfo('US/Eastern')
    
    while not shutdown_event.is_set():
        now = datetime.now(eastern)
        
        # Check if it's a weekday and time is 16:05 (4:05 PM)
        if now.weekday() < 5 and now.hour == 16 and now.minute == 5:
            print("[Agent SURYA] Generating Market Close Summary...")
            try:
                import reporting
                report_str = reporting.generate_report()
                if report_str:
                    notif.send_alert("📉 Market Close Summary", report_str, 0x00BFFF)
            except Exception as e:
                print(f"[Agent SURYA] Error generating EOD report: {e}")
                
            # Sleep 60 seconds to avoid firing multiple times in the same minute
            await asyncio.sleep(60)
            continue
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=30)
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
        run_chanakya_loop(),
        run_eod_report_loop(),
        run_premarket_reflection_loop()
    )
    print("[Orchestrator] Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
