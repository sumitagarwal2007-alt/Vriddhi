import asyncio
import os
import database as db
import ai_processor as ai
import market_data as md

async def test_database():
    print("--- Testing Database ---")
    await db.init_db()
    await db.log_signal("2026-06-04T12:00:00Z", "Apple releases new iPhone", "AAPL", "BULLISH", "Strong product launch", 1)
    await db.log_transaction("2026-06-04T12:01:00Z", "MOCK_ORDER_1", "AAPL", "BUY", 3.0, 150.0, "MARKET", "FILLED")
    await db.add_active_position("AAPL", 150.0, 3.0, 155.0, 0.05, "2026-06-04T12:01:00Z")
    
    positions = await db.get_active_positions()
    print(f"Active positions retrieved: {len(positions)}")
    for p in positions:
        print(p)
        
    await db.update_highest_price("AAPL", 160.0)
    print("Highest price updated")
    
    await db.remove_active_position("AAPL")
    positions_after = await db.get_active_positions()
    print(f"Active positions after removal: {len(positions_after)}")
    
def test_market_data():
    print("--- Testing Market Data ---")
    md.load_sp500_universe()
    is_aapl = md.is_eligible("AAPL")
    print(f"Is AAPL in S&P 500? {is_aapl}")
    
    # Missing API keys will return mock prices
    price = md.get_live_price("AAPL")
    print(f"Live Price (Mock if no keys): {price}")
    
    stop = md.calculate_dynamic_stop("AAPL", price)
    print(f"Dynamic stop: {stop}")

async def main():
    await test_database()
    test_market_data()
    print("All basic diagnostics passed.")

if __name__ == "__main__":
    asyncio.run(main())
