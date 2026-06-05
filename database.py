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
                is_eligible INTEGER
            )
        ''')
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
        await db.commit()

async def log_signal(timestamp: str, raw_headline: str, extracted_ticker: str, ai_sentiment: str, ai_reasoning: str, is_eligible: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO signals_log (timestamp, raw_headline, extracted_ticker, ai_sentiment, ai_reasoning, is_eligible)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (timestamp, raw_headline, extracted_ticker, ai_sentiment, ai_reasoning, is_eligible))
        await db.commit()

async def log_transaction(timestamp: str, alpaca_order_id: str, ticker: str, action: str, share_qty: float, execution_price: float, order_type: str, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO transactions (timestamp, alpaca_order_id, ticker, action, share_qty, execution_price, order_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, alpaca_order_id, ticker, action, share_qty, execution_price, order_type, status))
        await db.commit()

async def add_active_position(ticker: str, purchase_price: float, share_qty: float, highest_tracked_price: float, dynamic_stop_percent: float, entry_time: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR REPLACE INTO active_positions (ticker, purchase_price, share_qty, highest_tracked_price, dynamic_stop_percent, entry_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticker, purchase_price, share_qty, highest_tracked_price, dynamic_stop_percent, entry_time))
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
