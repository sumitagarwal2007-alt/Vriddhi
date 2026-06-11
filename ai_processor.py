import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from enum import Enum
from dotenv import load_dotenv
import httpx
import json

load_dotenv()

class Sentiment(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class TickerAnalysis(BaseModel):
    ticker: str = Field(description="Uppercase ticker symbol.")
    sentiment: Sentiment = Field(description="Strict Enum: BULLISH, BEARISH, or NEUTRAL.")
    significance_score: int = Field(description="Score from 1 to 10 indicating the magnitude and market impact of the news. 10 is massive.")
    reasoning: str = Field(description="Concise evaluation description text specifically for this ticker.")

class HeadlineAnalysis(BaseModel):
    analyses: List[TickerAnalysis] = Field(description="List of individual analyses for each relevant ticker found in the headline. If no tickers are found, this list should be empty.")

class AgentTenaliAnalysis(BaseModel):
    approved: bool = Field(description="Strict boolean: True if the trade is approved, False if rejected.")
    significance_score: int = Field(description="Audited score from 1 to 10. If approved is False, score must be <= 5.")
    critique: str = Field(description="Detail explaining why this signal is approved or rejected, checking for exit-liquidity, PR hype, retrospective news, dilution, or FOMO.")

import database as db

async def build_feedback_context() -> str:
    try:
        feedback = await db.get_recent_feedback(limit=15)
        latest_lessons = await db.get_latest_daily_lessons()
    except Exception as e:
        print(f"[Agent BIRBAL] Error fetching trade feedback: {e}")
        return ""
        
    if not feedback:
        return ""
        
    losses = []
    wins = []
    
    for f in feedback:
        headline = f.get('headline', 'Unknown')
        if headline == "Unknown headline" or f.get('ticker') == 'SH':
            continue
        pnl = f.get('pnl_pct', 0.0) * 100
        desc = f"- Ticker {f['ticker']} (PnL: {pnl:.2f}%): '{headline}' (Score: {f['significance_score']}) | Reason: {f['reasoning']}"
        if pnl < 0:
            losses.append(desc)
        else:
            wins.append(desc)
            
    context = "\n### CRITICAL: PAST PERFORMANCE FEEDBACK (SELF-LEARNING)\n"
    context += "You must learn from the outcomes of your previous trades. Avoid making the same classification mistakes.\n"
    
    if latest_lessons:
        context += f"\nDYNAMIC TRADING STRATEGY RULES GENERATED PRE-MARKET:\n{latest_lessons}\n"
        
    if losses:
        context += "\nRECENT TRADES THAT RESULTED IN LOSSES (DO NOT repeat these mistakes):\n"
        for l in losses[:8]:
            context += l + "\n"
        context += "Key takeaways from losses:\n"
        context += "- NEVER classify historical retrospect, retrospective backtest performance, or clickbait articles (e.g. 'If you invested $1000 X years ago...') as BULLISH or high-significance. These are NOT material news. Classify them as NEUTRAL and set significance_score to <= 5.\n"
        context += "- Avoid hyping standard, routine analyst target raises or upgrades (e.g. 'UBS maintains buy, raises target...') unless there is a fresh, substantial fundamental catalyst. These are often priced-in or momentum traps.\n"
        context += "- Avoid rating routine corporate announcements (e.g. minor partner updates, charity donations, or new hires) as highly significant BULLISH news.\n"
        
    if wins:
        context += "\nRECENT TRADES THAT RESULTED IN PROFITS (Emulate these patterns):\n"
        for w in wins[:5]:
            context += w + "\n"
            
    context += "\nEnsure that you adjust your evaluation criteria accordingly. Filter out clickbait/retrospective articles aggressively by setting them to NEUTRAL sentiment and low significance.\n"
    return context

client = None

def get_client():
    global client
    if client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "YOUR_GOOGLE_PRO_KEY":
            raise ValueError("GOOGLE_API_KEY is missing or not configured correctly.")
        client = genai.Client(api_key=api_key)
    return client

from tenacity import retry, wait_exponential, stop_after_attempt
from google.genai.errors import ClientError

async def _analyze_with_groq(headline: str) -> HeadlineAnalysis:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing or not configured.")
        
    system_prompt = """You are a highly capable financial sentiment analysis AI. 
Analyze the headline and output ONLY a raw JSON object matching this schema exactly:
{
  "analyses": [
    {
      "ticker": "TICKER1",
      "sentiment": "BULLISH", // Or BEARISH or NEUTRAL
      "significance_score": 8, // Integer from 1 to 10
      "reasoning": "Brief explanation specifically for this ticker"
    }
  ]
}"""

    feedback_context = await build_feedback_context()
    user_prompt = f"Analyze the following financial headline: {headline}"
    if feedback_context:
        user_prompt = f"{feedback_context}\n\nTask:\nAnalyze the following financial headline: {headline}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return HeadlineAnalysis.model_validate_json(content)

@retry(wait=wait_exponential(multiplier=2, min=4, max=20), stop=stop_after_attempt(6))
async def analyze_headline(headline: str) -> HeadlineAnalysis:
    """Analyzes a headline and extracts tickers, sentiment, and reasoning."""
    c = get_client()
    feedback_context = await build_feedback_context()
    user_prompt = f"Analyze the following financial headline: {headline}"
    if feedback_context:
        user_prompt = f"{feedback_context}\n\nTask:\nAnalyze the following financial headline: {headline}"
        
    try:
        response = await c.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=HeadlineAnalysis,
                temperature=0.1,
            ),
        )
        return HeadlineAnalysis.model_validate_json(response.text)
    except ClientError as e:
        print(f"[Agent BIRBAL] Gemini API Rate Limit or ClientError detected. Falling back to Groq Llama 3...")
        return await _analyze_with_groq(headline)

async def _analyze_tenali_with_groq(headline: str, ticker: str, birbal_reasoning: str) -> AgentTenaliAnalysis:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing or not configured.")
        
    system_prompt = """You are Agent TENALI, a Contrarian Quantitative Risk Auditor and Devil's Advocate. 
Your job is to critically audit the bullish sentiment parsed by Agent BIRBAL for a specific ticker.
Evaluate if the news is a potential trap. Output ONLY a raw JSON object matching this schema exactly:
{
  "approved": true, // or false
  "significance_score": 8, // Integer from 1 to 10. If approved is false, set score <= 5.
  "critique": "Your critical evaluation"
}"""

    feedback_context = await build_feedback_context()
    user_prompt = f"Ticker to audit: {ticker}\nHeadline: {headline}\nBirbal's Reasoning: {birbal_reasoning}"
    if feedback_context:
        user_prompt = f"{feedback_context}\n\nTask:\nTicker to audit: {ticker}\nHeadline: {headline}\nBirbal's Reasoning: {birbal_reasoning}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return AgentTenaliAnalysis.model_validate_json(content)

@retry(wait=wait_exponential(multiplier=2, min=4, max=20), stop=stop_after_attempt(6))
async def analyze_headline_tenali(headline: str, ticker: str, birbal_reasoning: str) -> AgentTenaliAnalysis:
    """Invokes Agent Tenali to audit the bullish headline sentiment."""
    c = get_client()
    feedback_context = await build_feedback_context()
    user_prompt = f"Ticker to audit: {ticker}\nHeadline: {headline}\nBirbal's Reasoning: {birbal_reasoning}"
    if feedback_context:
        user_prompt = f"{feedback_context}\n\nTask:\nTicker to audit: {ticker}\nHeadline: {headline}\nBirbal's Reasoning: {birbal_reasoning}"
        
    try:
        response = await c.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are Agent TENALI, a Contrarian Quantitative Risk Auditor and Devil's Advocate. Your job is to critically audit the bullish sentiment parsed by Agent BIRBAL for a specific ticker. Evaluate if the news is a potential trap.",
                response_mime_type="application/json",
                response_schema=AgentTenaliAnalysis,
                temperature=0.1,
            ),
        )
        return AgentTenaliAnalysis.model_validate_json(response.text)
    except ClientError as e:
        print(f"[Agent TENALI] Gemini API Rate Limit or ClientError detected. Falling back to Groq Llama 3...")
        return await _analyze_tenali_with_groq(headline, ticker, birbal_reasoning)


import aiosqlite
import sqlite3

async def generate_daily_reflective_lessons(trade_date: str) -> str:
    """Summarizes trades closed on trade_date and prompts Gemini/Llama to generate actionable rule feedback."""
    trades = []
    async with aiosqlite.connect(db.DB_NAME) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM trade_feedback WHERE DATE(timestamp) = ? ORDER BY timestamp ASC", (trade_date,)) as cursor:
            rows = await cursor.fetchall()
            trades = [dict(r) for r in rows]
            
    if not trades:
        return "No trades executed on this date."
        
    # Summarize trades
    wins = 0
    losses = 0
    total_pnl = 0.0
    trade_details = ""
    
    for t in trades:
        pnl = t['pnl_pct'] * 100
        if pnl >= 0:
            wins += 1
        else:
            losses += 1
        total_pnl += pnl
        trade_details += f"- Ticker {t['ticker']} | PnL: {pnl:.2f}% | Buy: ${t['buy_price']:.2f} | Sell: ${t['sell_price']:.2f} | Catalyst: {t['headline']} | Birbal Score: {t['significance_score']}/10 | Tenali Score: {t.get('tenali_score', 0)}/10 | Critique: {t.get('tenali_critique', 'N/A')}\n"
        
    avg_pnl = total_pnl / len(trades)
    
    summary_report = f"""
    Trade Summary for Date: {trade_date}
    Total Trades: {len(trades)} (Wins: {wins} | Losses: {losses})
    Average Trade Performance: {avg_pnl:.2f}%
    
    Trade Details:
    {trade_details}
    """
    
    system_prompt = """You are the Master Trading Strategist for Vriddhi Quant. 
    Review the trading post-mortem report and identify mistakes or patterns of success/failures. 
    Write exactly 4-5 bullet points of clear, actionable rules/lessons (in standard markdown formatting) for Agent Birbal and Agent Tenali to follow in today's trading loop.
    Focus on correcting stop-loss parameters, catalyst conviction, or sentiment classification errors. 
    Make the rules general to stock categories or catalyst characteristics; DO NOT mention specific stock tickers in the lessons (e.g. write 'avoid minor routine partnership announcements' instead of 'never buy TMUS'). Keep it extremely concise and direct."""
    
    user_prompt = f"Here is the trade report:\n{summary_report}\n\nTask: Output a raw markdown block containing the 4-5 actionable lessons for today's trading."
    
    try:
        c = get_client()
        response = await c.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
            ),
        )
        lessons_text = response.text
    except Exception as e:
        print(f"[Self-Learning Orchestrator] Gemini error: {e}. Falling back to Groq Llama 3 for reflection...")
        lessons_text = await _generate_lessons_with_groq(system_prompt, user_prompt)
        
    # Save lessons to database
    await db.save_daily_lessons(trade_date, lessons_text)
    return lessons_text

async def _generate_lessons_with_groq(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Groq key missing - could not generate lessons."
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2
                },
                timeout=12.0
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[Self-Learning Orchestrator] Groq error: {e}")
            return "Error generating lessons via Groq Llama 3."
