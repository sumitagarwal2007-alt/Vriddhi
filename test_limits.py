import asyncio
import os
import time
from dotenv import load_dotenv
from google import genai
import httpx
from google.genai.errors import ClientError

load_dotenv()

async def test_gemini_burst():
    """Test Gemini Requests Per Minute (RPM) limit."""
    print("\n--- Testing Gemini API Limits ---")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY missing!")
        return

    client = genai.Client(api_key=api_key)
    success_count = 0
    
    print("Firing rapid requests to Gemini to find the RPM ceiling...")
    for i in range(1, 101):
        try:
            # We use an async thread to fire them fast, or just await them one by one.
            # Using sync call in a loop is fast enough to hit a 15 RPM limit.
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Test message {i}. Reply with a single word."
            )
            success_count += 1
            print(f"✅ Gemini Request {i}: Success")
            
        except ClientError as e:
            print(f"🛑 Gemini Rate Limit Hit at request {i}!")
            print(f"Error Details: {e}")
            break
        except Exception as e:
            print(f"❌ Unexpected Gemini error: {e}")
            break

    print(f"Gemini Total Successful Requests before blocking: {success_count}")


async def test_groq_burst():
    """Test Groq Requests Per Minute (RPM) limit."""
    print("\n--- Testing Groq API Limits ---")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY missing!")
        return

    success_count = 0
    print("Firing rapid requests to Groq to find the RPM ceiling...")
    
    async with httpx.AsyncClient() as client:
        for i in range(1, 201):
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": f"Test message {i}. Reply with a single word."}]
                    },
                    timeout=10.0
                )
                if response.status_code == 429:
                    print(f"🛑 Groq Rate Limit Hit at request {i}!")
                    print(f"Error Details: {response.text}")
                    break
                    
                response.raise_for_status()
                success_count += 1
                print(f"✅ Groq Request {i}: Success")
                
            except Exception as e:
                print(f"❌ Unexpected Groq error: {e}")
                break

    print(f"Groq Total Successful Requests before blocking: {success_count}")

async def main():
    print("⚠️ WARNING: This will consume a portion of your daily quotas!")
    await asyncio.sleep(2)
    
    await test_gemini_burst()
    await asyncio.sleep(2)
    await test_groq_burst()

if __name__ == "__main__":
    asyncio.run(main())
