import asyncio
import database as db

async def run_tests():
    print("--- TESTING NIGHT WATCH SCHEMA ---")
    await db.init_db()
    print("DB initialized successfully.")
    
    # Add fake overnight position
    await db.add_to_waitlist(
        ticker="AAPL",
        initial_price=150.0,
        target_buy_time="2026-06-08T09:00:00",
        headline="Apple makes car",
        stop_percent=0.05,
        is_overnight=1
    )
    
    waitlist = await db.get_waitlist()
    found = False
    for w in waitlist:
        if w['ticker'] == 'AAPL':
            found = True
            print(f"Found AAPL in waitlist: is_overnight = {w['is_overnight']}")
            assert w['is_overnight'] == 1
    
    if found:
        print("Night Watch waitlist schema works perfectly!")
        await db.remove_from_waitlist("AAPL")
    else:
        print("Failed to find AAPL in waitlist.")
        
if __name__ == "__main__":
    asyncio.run(run_tests())
