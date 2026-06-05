import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class Sentiment(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class HeadlineAnalysis(BaseModel):
    tickers_found: List[str] = Field(description="Array of uppercase target strings.")
    sentiment: Sentiment = Field(description="Strict Enum: BULLISH, BEARISH, or NEUTRAL.")
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

async def analyze_headline(headline: str) -> HeadlineAnalysis:
    """Analyzes a headline and extracts tickers, sentiment, and reasoning."""
    c = get_client()
    # We use sync generate_content here because google.genai async client exists but this is simple enough.
    # To not block event loop, we can run it in an executor, or if the client supports async we use it.
    # google.genai supports async through `client.aio.models.generate_content`.
    response = await c.aio.models.generate_content(
        model='gemini-2.5-pro',
        contents=f"Analyze the following financial headline: {headline}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=HeadlineAnalysis,
            temperature=0.1,
        ),
    )
    return HeadlineAnalysis.model_validate_json(response.text)
