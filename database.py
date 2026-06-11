import aiosqlite
import sqlite3
from typing import Optional, List, Dict, Any

DB_NAME = "trading_agent.db"

async def init_db():
    """Initializes the database and creates necessary tables."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS signals_log (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                raw_headline TEXT,
                extracted_ticker TEXT,
                ai_sentiment TEXT,
                ai_reasoning TEXT,
                is_eligible INTEGER,
                significance_score INTEGER
            )
        ''')
        # Alpha V2 Upgrade: Add significance_score to signals_log
        try:
            await db.execute('ALTER TABLE signals_log ADD COLUMN significance_score INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # Alpha-3 Upgrade: Add Agent Tenali audit columns to signals_log
        try:
            await db.execute('ALTER TABLE signals_log ADD COLUMN tenali_approved INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass
        try:
            await db.execute('ALTER TABLE signals_log ADD COLUMN tenali_critique TEXT DEFAULT ""')
        except sqlite3.OperationalError:
            pass
        try:
            await db.execute('ALTER TABLE signals_log ADD COLUMN tenali_score INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                alpaca_order_id TEXT,
                ticker TEXT,
                action TEXT,
                share_qty REAL,
                execution_price REAL,
                order_type TEXT,
                status TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS active_positions (
                ticker TEXT PRIMARY KEY,
                purchase_price REAL,
                share_qty REAL,
                highest_tracked_price REAL,
                dynamic_stop_percent REAL,
                entry_time TEXT
            )
        ''')
        # Alpha V2 Upgrade: Add profit_taken to active_positions
        try:
            await db.execute('ALTER TABLE active_positions ADD COLUMN profit_taken INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # Alpha-3 Upgrade: Add significance_score to active_positions
        try:
            await db.execute('ALTER TABLE active_positions ADD COLUMN significance_score INTEGER DEFAULT 7')
        except sqlite3.OperationalError:
            pass
            
        await db.execute('''
            CREATE TABLE IF NOT EXISTS waitlist_positions (
                ticker TEXT PRIMARY KEY,
                initial_price REAL,
                target_buy_time TEXT,
                headline TEXT,
                stop_percent REAL
            )
        ''')
        # Night Watch Upgrade: Add is_overnight to waitlist_positions
        try:
            await db.execute('ALTER TABLE waitlist_positions ADD COLUMN is_overnight INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # Alpha-3 Upgrade: Add significance_score to waitlist_positions
        try:
            await db.execute('ALTER TABLE waitlist_positions ADD COLUMN significance_score INTEGER DEFAULT 7')
        except sqlite3.OperationalError:
            pass
            
        # Self-Learning Upgrade: Add trade_feedback table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trade_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                headline TEXT,
                sentiment TEXT,
                significance_score INTEGER,
                reasoning TEXT,
                buy_price REAL,
                sell_price REAL,
                pnl_pct REAL,
                timestamp TEXT
            )
        ''')
        # Alpha-3 Upgrade: Add Agent Tenali audit columns to trade_feedback
        try:
            await db.execute('ALTER TABLE trade_feedback ADD COLUMN tenali_critique TEXT DEFAULT ""')
        except sqlite3.OperationalError:
            pass
        try:
            await db.execute('ALTER TABLE trade_feedback ADD COLUMN tenali_score INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
            
        # Self-Learning Upgrade: Add daily_lessons table to store pre-market reflection insights
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                lessons TEXT
            )
        ''')
        await db.commit()


async def save_daily_lessons(date_str: str, lessons_text: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR REPLACE INTO daily_lessons (date, lessons)
            VALUES (?, ?)
        ''', (date_str, lessons_text))
        await db.commit()

async def get_latest_daily_lessons() -> Optional[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT lessons FROM daily_lessons ORDER BY date DESC LIMIT 1') as cursor:
            row = await cursor.fetchone()
            return row['lessons'] if row else None


async def log_signal(timestamp: str, raw_headline: str, extracted_ticker: str, ai_sentiment: str, ai_reasoning: str, is_eligible: int, significance_score: int = 0, tenali_approved: int = 1, tenali_critique: str = "", tenali_score: int = 0):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO signals_log (timestamp, raw_headline, extracted_ticker, ai_sentiment, ai_reasoning, is_eligible, significance_score, tenali_approved, tenali_critique, tenali_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, raw_headline, extracted_ticker, ai_sentiment, ai_reasoning, is_eligible, significance_score, tenali_approved, tenali_critique, tenali_score))
        await db.commit()

async def log_transaction(timestamp: str, alpaca_order_id: str, ticker: str, action: str, share_qty: float, execution_price: float, order_type: str, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO transactions (timestamp, alpaca_order_id, ticker, action, share_qty, execution_price, order_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, alpaca_order_id, ticker, action, share_qty, execution_price, order_type, status))
        await db.commit()

async def add_active_position(ticker: str, purchase_price: float, share_qty: float, highest_tracked_price: float, dynamic_stop_percent: float, entry_time: str, profit_taken: int = 0, significance_score: int = 7):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR REPLACE INTO active_positions (ticker, purchase_price, share_qty, highest_tracked_price, dynamic_stop_percent, entry_time, profit_taken, significance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, purchase_price, share_qty, highest_tracked_price, dynamic_stop_percent, entry_time, profit_taken, significance_score))
        await db.commit()

async def get_active_positions() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM active_positions') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def update_highest_price(ticker: str, new_high: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE active_positions SET highest_tracked_price = ? WHERE ticker = ?
        ''', (new_high, ticker))
        await db.commit()

async def remove_active_position(ticker: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            DELETE FROM active_positions WHERE ticker = ?
        ''', (ticker,))
        await db.commit()

async def mark_profit_taken(ticker: str, new_qty: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE active_positions SET profit_taken = 1, share_qty = ? WHERE ticker = ?
        ''', (new_qty, ticker))
        await db.commit()

async def add_to_waitlist(ticker: str, initial_price: float, target_buy_time: str, headline: str, stop_percent: float, is_overnight: int = 0, significance_score: int = 7):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR REPLACE INTO waitlist_positions (ticker, initial_price, target_buy_time, headline, stop_percent, is_overnight, significance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, initial_price, target_buy_time, headline, stop_percent, is_overnight, significance_score))
        await db.commit()

async def get_waitlist() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM waitlist_positions') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def remove_from_waitlist(ticker: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM waitlist_positions WHERE ticker = ?', (ticker,))
        await db.commit()

async def wipe_all_active_positions():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM active_positions')
        await db.commit()

async def log_trade_feedback(ticker: str, sell_price: float, timestamp: str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT purchase_price, entry_time FROM active_positions WHERE ticker = ?', (ticker,)) as cursor:
            pos = await cursor.fetchone()
            if not pos:
                return
            purchase_price = pos['purchase_price']
            entry_time = pos['entry_time']
        
        async with db.execute('''
            SELECT raw_headline, ai_sentiment, significance_score, ai_reasoning, tenali_critique, tenali_score
            FROM signals_log 
            WHERE extracted_ticker = ? AND ai_sentiment = 'BULLISH' AND timestamp <= ? 
            ORDER BY timestamp DESC LIMIT 1
        ''', (ticker, entry_time)) as cursor:
            sig = await cursor.fetchone()
            if sig:
                headline = sig['raw_headline']
                sentiment = sig['ai_sentiment']
                significance_score = sig['significance_score']
                reasoning = sig['ai_reasoning']
                tenali_critique = sig.get('tenali_critique', '')
                tenali_score = sig.get('tenali_score', 0)
            else:
                headline = "Unknown headline"
                sentiment = "BULLISH"
                significance_score = 0
                reasoning = "N/A"
                tenali_critique = ""
                tenali_score = 0
                
        pnl_pct = (sell_price - purchase_price) / purchase_price
        
        await db.execute('''
            INSERT INTO trade_feedback (ticker, headline, sentiment, significance_score, reasoning, buy_price, sell_price, pnl_pct, timestamp, tenali_critique, tenali_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, headline, sentiment, significance_score, reasoning, purchase_price, sell_price, pnl_pct, timestamp, tenali_critique, tenali_score))
        await db.commit()

async def get_recent_feedback(limit: int = 10) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trade_feedback ORDER BY timestamp DESC LIMIT ?', (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_latest_trade_date() -> Optional[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT DATE(timestamp) as trade_date FROM trade_feedback ORDER BY timestamp DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            return row['trade_date'] if row else None

async def get_lessons_for_date(trade_date: str) -> Optional[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT lessons FROM daily_lessons WHERE date = ?", (trade_date,)) as cursor:
            row = await cursor.fetchone()
            return row['lessons'] if row else None

async def get_unanalyzed_trade_dates() -> List[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT DISTINCT DATE(timestamp) as trade_date "
            "FROM trade_feedback "
            "WHERE DATE(timestamp) NOT IN (SELECT date FROM daily_lessons) "
            "ORDER BY trade_date ASC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [row['trade_date'] for row in rows]


