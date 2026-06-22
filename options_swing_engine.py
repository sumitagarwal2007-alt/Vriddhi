import asyncio
import options_data
import market_data as md
import ai_processor
import notifications as notif
from datetime import datetime
import traceback

# Core Watchlist for Swing/LEAPS Strategy (Large Caps with potential recovery catalysts)
WATCHLIST = ["AAPL", "TSLA", "META", "GOOGL", "AMZN", "MSFT", "NVDA", "AMD", "PLTR", "SNOW"]

import requests
import os
from datetime import timedelta
import database as db
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest

def get_options_client():
    api_key = os.getenv("ALPACA_OPTIONS_API_KEY")
    secret_key = os.getenv("ALPACA_OPTIONS_SECRET_KEY")
    if api_key and secret_key:
        return TradingClient(api_key, secret_key, paper=True)
    return None

def fetch_recent_news(ticker: str):
    token = os.getenv("FINNHUB_TOKEN")
    if not token or token == "YOUR_FINNHUB_KEY":
        return []
    
    end = datetime.now()
    start = end - timedelta(days=3)
    
    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start.strftime('%Y-%m-%d')}&to={end.strftime('%Y-%m-%d')}&token={token}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            headlines = [item['headline'] for item in data[:3]]
            return headlines
    except:
        pass
    return []

async def run_daily_analysis():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Brendan's 4-Layer Options & Swing Engine...")
    
    # ---------------------------------------------------------
    # LAYER 3: Macro Context
    # ---------------------------------------------------------
    print("Fetching Macro Context...")
    macro = options_data.get_market_context()
    
    macro_env = macro['Environment']
    vix = macro['VIX']
    spy_trend = macro['SPY_5D_Trend']
    
    print(f"Macro Score: {macro['Macro_Score']}/10 (VIX: {vix}, SPY 5D: {spy_trend}%)")
    
    # ---------------------------------------------------------
    # LAYER 3 (cont): AI Screener for Recovery Catalysts
    # ---------------------------------------------------------
    print("Screening watchlist for recovery catalysts...")
    bullish_targets = []
    
    for ticker in WATCHLIST:
        print(f"  -> Scanning {ticker}...")
        headlines = fetch_recent_news(ticker)
        if not headlines:
            continue
            
        combined_headline = " | ".join(headlines)
        
        try:
            results = await ai_processor.analyze_headline(combined_headline)
            if results and results.analyses:
                for res in results.analyses:
                    if res.ticker == ticker and res.sentiment.value == "BULLISH" and res.significance_score >= 6:
                        bullish_targets.append({
                            "ticker": ticker,
                            "score": res.significance_score,
                            "reasoning": res.reasoning
                        })
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            
    # Sort targets by significance
    bullish_targets.sort(key=lambda x: x["score"], reverse=True)
    
    # ---------------------------------------------------------
    # LAYER 1 & 2: Options Data & Analytics
    # ---------------------------------------------------------
    recommendations = []
    
    # We only process the top 3 setups to keep the report focused
    for target in bullish_targets[:3]:
        ticker = target['ticker']
        print(f"Pulling LEAPS Options Chain for {ticker}...")
        try:
            chain_df = options_data.get_leaps_options_chain(ticker, min_days_to_expiration=45)
            if chain_df.empty:
                continue
                
            # Filter for ITM/ATM calls (Delta around 0.60 to 0.80) to minimize Theta burn while capturing directional upside
            target_calls = chain_df[(chain_df['delta'] >= 0.60) & (chain_df['delta'] <= 0.85)]
            if target_calls.empty:
                # Fallback to closest ATM
                target_calls = chain_df.iloc[(chain_df['strike'] - chain_df['spot_price']).abs().argsort()[:1]]
                
            # Pick the contract with the highest open interest among the filtered
            best_contract = target_calls.sort_values(by='open_interest', ascending=False).iloc[0]
            
            recommendations.append({
                "ticker": ticker,
                "spot": best_contract['spot_price'],
                "expiration": best_contract['expiration'],
                "strike": best_contract['strike'],
                "ask": best_contract['ask'],
                "delta": best_contract['delta'],
                "theta": best_contract['theta'],
                "iv": best_contract['iv'],
                "contract_symbol": best_contract['contract_symbol'],
                "reasoning": target['reasoning']
            })
        except Exception as e:
            print(f"Error fetching options for {ticker}: {e}")
            
    # ---------------------------------------------------------
    # LAYER 4: Alerts and Dashboarding
    # ---------------------------------------------------------
    print("Dispatching Daily EOD Report...")
    
    report_title = "📊 EOD Options & Swing Analysis"
    report_desc = f"**Macro Environment**: {macro_env}\\n**VIX**: {vix}\\n**SPY 5D Trend**: {spy_trend}%\\n\\n"
    
    if not recommendations:
        report_desc += "No high-probability LEAPS or Swing setups detected today."
        notif.send_alert(report_title, report_desc, color=0x808080)
        return
        
    report_desc += "🎯 **AI-Verified Institutional LEAPS Targets:**\\n\\n"
    
    # Discord supports 25 fields max, we will add them nicely
    fields = {}
    for i, rec in enumerate(recommendations):
        ticker = rec['ticker']
        spot = rec['spot']
        exp = rec['expiration']
        strike = rec['strike']
        ask = rec['ask']
        delta = rec['delta']
        theta = rec['theta']
        reason = rec['reasoning']
        
        # We append to report_desc for email fallback, and use fields for Discord Embed
        trade_summary = f"Strike: ${strike:.2f} | Exp: {exp} | Ask: ${ask:.2f}\\nDelta: {delta:.2f} | Theta: {theta:.2f}\\nSpot: ${spot:.2f}"
        
        fields[f"{ticker} Call Option Setup"] = trade_summary
        report_desc += f"**{ticker}** ({exp} ${strike:.2f}C)\\n{reason}\\n\\n"
        
    # Execute Options Orders and Log
    options_client = get_options_client()
    for rec in recommendations:
        ticker = rec['ticker']
        contract = rec['contract_symbol']
        try:
            if options_client:
                print(f"Submitting Options Order to Alpaca for {contract}...")
                order_data = MarketOrderRequest(
                    symbol=contract,
                    qty=1,
                    side='buy',
                    time_in_force='day'
                )
                order = options_client.submit_order(order_data)
                alpaca_order_id = str(order.id)
            else:
                alpaca_order_id = "SIMULATED_OPT_ORDER"
                
            # Log to DB
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # We buy 1 contract (represents 100 shares, but alpaca options qty is contracts)
            await db.log_transaction(ts, alpaca_order_id, contract, "BUY", 1.0, rec['ask'], "MARKET", "FILLED", "OPTIONS_SWING")
            await db.add_active_position(
                ticker=contract, # Use contract symbol as ticker for tracking
                purchase_price=rec['ask'],
                share_qty=1.0,
                highest_tracked_price=rec['ask'],
                dynamic_stop_percent=0.20, # Options have wider stops
                entry_time=ts,
                strategy_tag="OPTIONS_SWING"
            )
            print(f"Logged Option Position {contract} to Database.")
        except Exception as e:
            print(f"Failed to execute/log order for {contract}: {e}")

    notif.send_alert(report_title, report_desc, color=0x9333ea, fields=fields)
    print("Engine cycle complete.")

if __name__ == "__main__":
    try:
        asyncio.run(run_daily_analysis())
    except Exception as e:
        print(f"Fatal error in Swing Engine: {e}")
        traceback.print_exc()
