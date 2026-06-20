import asyncio
import os
import ai_processor as ai

# Set mock environment variables if needed, but we have real ones loaded from .env
# Let's print the feedback prompt text to verify what it's generating
async def verify_feedback_generation():
    print("=" * 50)
    print("VERIFYING FEEDBACK GENERATION")
    print("=" * 50)
    feedback_context = await ai.build_feedback_context()
    print(feedback_context)
    print("=" * 50)

async def test_headlines():
    headlines_to_test = [
        # Retrospective clickbait
        "If You Invested $1000 In Broadcom Stock 15 Years Ago, You Would Have This Much Today",
        "Here's How Much You Would Have Made Owning Synopsys Stock In The Last 20 Years",
        
        # Routine analyst target raises
        "UBS Maintains Buy on Lam Research, Raises Price Target to $375",
        "B of A Securities Maintains Buy on Datadog, Raises Price Target to $280",
        
        # Real material news
        "Incyte Bets $1.25 Billion On Rare Bleeding Disorder Drug With Blockbuster Potential",
        "Super Micro Announces $7B Equity And Convertible Financing To Fund The Purchase Of Components To Satisfy The AI Orders"
    ]
    
    print("\n" + "=" * 50)
    print("TESTING HEADLINES WITH SELF-LEARNING PROMPT")
    print("=" * 50)
    
    for headline in headlines_to_test:
        print(f"\nHeadline: '{headline}'")
        try:
            analysis = await ai.analyze_headline(headline)
            for a in analysis.analyses:
                print(f"  -> Ticker: {a.ticker}")
                print(f"     Sentiment: {a.sentiment.value}")
                print(f"     Significance Score: {a.significance_score}")
                print(f"     Reasoning: {a.reasoning}")
        except Exception as e:
            print(f"  Error analyzing: {e}")
            
    print("=" * 50)

async def main():
    await verify_feedback_generation()
    await test_headlines()

if __name__ == '__main__':
    asyncio.run(main())
