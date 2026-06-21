import asyncio
import ai_processor

async def run_test():
    headline = "NVIDIA absolutely crushes Q3 earnings expectations, announcing a surprise 5-for-1 stock split and raising forward guidance by 40% due to unprecedented AI chip demand."
    
    print(f"\n📰 INCOMING HEADLINE: '{headline}'")
    print("-" * 60)
    print("🧠 Agent BIRBAL (Gemini Pro) is analyzing...\n")
    
    results = await ai_processor.analyze_headline(headline)
    
    if not results or not results.analyses:
        print("Birbal determined there was no actionable S&P 500 news here.")
    else:
        for res in results.analyses:
            print(f"🎯 TICKER: {res.ticker}")
            print(f"📊 SENTIMENT: {res.sentiment.value}")
            print(f"🔥 SIGNIFICANCE: {res.significance_score}/10")
            print(f"📝 REASONING: {res.reasoning}")
            print("-" * 60)
            
if __name__ == "__main__":
    asyncio.run(run_test())
