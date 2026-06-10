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
