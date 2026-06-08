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

class HeadlineAnalysis(BaseModel):
    tickers_found: List[str] = Field(description="Array of uppercase target strings.")
    sentiment: Sentiment = Field(description="Strict Enum: BULLISH, BEARISH, or NEUTRAL.")
    significance_score: int = Field(description="Score from 1 to 10 indicating the magnitude and market impact of the news. 10 is massive.")
    reasoning: str = Field(description="Concise evaluation description text.")

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
  "tickers_found": ["TICKER1", "TICKER2"],
  "sentiment": "BULLISH", // Or BEARISH or NEUTRAL
  "significance_score": 8, // Integer from 1 to 10
  "reasoning": "Brief explanation"
}"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze the following financial headline: {headline}"}
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
    try:
        response = await c.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Analyze the following financial headline: {headline}",
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
