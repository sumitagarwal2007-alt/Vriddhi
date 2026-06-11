import asyncio
from datetime import datetime
import database as db

async def test_reflection_logic():
    print("=" * 60)
    print("Testing get_unanalyzed_trade_dates Helper")
    print("=" * 60)
    
    unanalyzed_dates = await db.get_unanalyzed_trade_dates()
    print(f"Unanalyzed trade dates in database: {unanalyzed_dates}")
    
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        import pytz as tz
        ZoneInfo = lambda x: tz.timezone(x)
        
    eastern = ZoneInfo('US/Eastern')
    now_est = datetime.now(eastern)
    current_date_str = now_est.strftime('%Y-%m-%d')
    print(f"Current Eastern time: {now_est.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Current date: {current_date_str}")
    
    for date_str in unanalyzed_dates:
        is_completed = False
        reason = ""
        if date_str < current_date_str:
            is_completed = True
            reason = "Date is in the past."
        elif date_str == current_date_str:
            if now_est.hour > 16 or (now_est.hour == 16 and now_est.minute >= 5):
                is_completed = True
                reason = "Date is today, and it is after 4:05 PM EST."
            else:
                reason = "Date is today, but it is before 4:05 PM EST."
        else:
            reason = "Date is in the future."
            
        print(f"Date: {date_str} | Completed: {is_completed} | Reason: {reason}")
        
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(test_reflection_logic())
