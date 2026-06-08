import asyncio
import os
from dotenv import load_dotenv
import ai_processor as ai

load_dotenv()

async def test_groq():
    print("--- Testing Groq API Fallback ---")
    if not os.getenv("GROQ_API_KEY"):
        print("❌ Error: GROQ_API_KEY not found in .env or environment!")
        return
        
    print("Sending headline to Groq API...")
    try:
        headline = "NVIDIA surges 5% after signing new massive cloud deal with Microsoft"
        # We will directly call the fallback function for testing
        analysis = await ai._analyze_with_groq(headline)
        print("✅ Groq Fallback Success!")
        print(f"Sentiment: {analysis.sentiment}")
        print(f"Tickers: {analysis.tickers_found}")
        print(f"Reasoning: {analysis.reasoning}")
        print(f"Score: {analysis.significance_score}")
    except Exception as e:
        print(f"❌ Error during Groq fallback: {e}")

if __name__ == "__main__":
    asyncio.run(test_groq())
