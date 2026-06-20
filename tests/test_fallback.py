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
        headline = "Michael Burry Sees Echoes Of His 2019 GameStop Bet In Lululemon: 'The Last Time I Owned A Stock As Hated...'"
        # We will directly call the fallback function for testing
        analysis = await ai._analyze_with_groq(headline)
        print("✅ Groq Fallback Success!")
        print(f"Found {len(analysis.analyses)} ticker(s).")
        for t in analysis.analyses:
            print(f"\nTicker: {t.ticker}")
            print(f"Sentiment: {t.sentiment.value}")
            print(f"Score: {t.significance_score}")
            print(f"Reasoning: {t.reasoning}")
    except Exception as e:
        print(f"❌ Error during Groq fallback: {e}")

if __name__ == "__main__":
    asyncio.run(test_groq())
