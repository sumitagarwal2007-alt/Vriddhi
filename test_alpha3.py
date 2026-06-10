import asyncio
import os
import database as db
import ai_processor as ai
import market_data as md

async def test_consensus():
    print("\n--- Testing Multi-Agent Consensus (Birbal + Tenali) ---")
    
    # 1. Real bullish fundamental catalyst
    headline_1 = "NVIDIA announces record-breaking Q3 earnings, beats consensus estimates by 25%"
    print(f"\nHeadline: '{headline_1}'")
    birbal_analysis_1 = await ai.analyze_headline(headline_1)
    
    for analysis in birbal_analysis_1.analyses:
        print(f"[Agent BIRBAL] Ticker: {analysis.ticker}, Sentiment: {analysis.sentiment.value}, Score: {analysis.significance_score}")
        if analysis.sentiment.value == "BULLISH":
            tenali_analysis_1 = await ai.analyze_headline_tenali(headline_1, analysis.ticker, analysis.reasoning)
            print(f"[Agent TENALI] Approved: {tenali_analysis_1.approved}, Score: {tenali_analysis_1.significance_score}")
            print(f"[Agent TENALI] Critique: {tenali_analysis_1.critique}")
            
    # 2. Retrospective clickbait article (should be audited and rejected by Tenali)
    headline_2 = "If you had bought $1000 of Apple (AAPL) stock 15 years ago, here is how much you would have today"
    print(f"\nHeadline: '{headline_2}'")
    birbal_analysis_2 = await ai.analyze_headline(headline_2)
    
    for analysis in birbal_analysis_2.analyses:
        print(f"[Agent BIRBAL] Ticker: {analysis.ticker}, Sentiment: {analysis.sentiment.value}, Score: {analysis.significance_score}")
        if analysis.sentiment.value == "BULLISH":
            tenali_analysis_2 = await ai.analyze_headline_tenali(headline_2, analysis.ticker, analysis.reasoning)
            print(f"[Agent TENALI] Approved: {tenali_analysis_2.approved}, Score: {tenali_analysis_2.significance_score}")
            print(f"[Agent TENALI] Critique: {tenali_analysis_2.critique}")

def test_dynamic_position_sizing():
    print("\n--- Testing Dynamic Risk Position Sizing ---")
    
    # Baseline stop loss: 2.5%
    stop = 0.025
    
    # Moderate significance, flat market
    size_1 = md.calculate_position_size(stop_percent=stop, significance_score=7, portfolio_equity=10000.0, spy_momentum=0.0)
    # High significance, bullish market
    size_2 = md.calculate_position_size(stop_percent=stop, significance_score=9, portfolio_equity=10000.0, spy_momentum=0.005)
    # Low significance, bearish market
    size_3 = md.calculate_position_size(stop_percent=stop, significance_score=6, portfolio_equity=10000.0, spy_momentum=-0.005)
    
    print(f"Size 1 (Score 7, SPY Flat):  ${size_1:.2f} (Expected risk: $20)")
    print(f"Size 2 (Score 9, SPY Bull):  ${size_2:.2f} (Expected risk: $20 * 1.5 * 1.2 = $36)")
    print(f"Size 3 (Score 6, SPY Bear):  ${size_3:.2f} (Expected risk: $20 * 0.5 * 0.8 = $8)")

async def test_db_logging():
    print("\n--- Testing Database Logging for Tenali ---")
    await db.init_db()
    
    timestamp = "2026-06-10T12:00:00Z"
    await db.log_signal(
        timestamp=timestamp,
        raw_headline="MOCK HEADLINE",
        extracted_ticker="MOCK",
        ai_sentiment="BULLISH",
        ai_reasoning="Good stuff",
        is_eligible=1,
        significance_score=8,
        tenali_approved=1,
        tenali_critique="Tenali approves because it looks fundamental",
        tenali_score=8
    )
    print("Logged test signal successfully.")
    
    # Retrieve from DB using simple query
    import sqlite3
    conn = sqlite3.connect("trading_agent.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM signals_log ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    print("Retrieved Logged Row:")
    print(row)

async def main():
    await test_db_logging()
    test_dynamic_position_sizing()
    await test_consensus()

if __name__ == "__main__":
    asyncio.run(main())
