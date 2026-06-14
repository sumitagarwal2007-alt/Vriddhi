import os
import json
import time
import hashlib
import traceback
from datetime import datetime
from google import genai
from google.genai import types

REPORTS_FILE = "anomaly_reports.json"
CACHE_FILE = "anomaly_cache.json"
COOLDOWN_SECONDS = 3600 # 1 hour cooldown for identical crashes

client = None

def get_client():
    global client
    if client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "YOUR_GOOGLE_PRO_KEY":
            raise ValueError("GOOGLE_API_KEY is missing")
        client = genai.Client(api_key=api_key)
    return client

def _get_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(cache):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"[SRE] Error saving cache: {e}")

async def diagnose_crash(loop_name: str, exception: Exception, tb_str: str) -> str:
    """Diagnoses a crash using Gemini and logs it, respecting rate limits."""
    print(f"[SRE] Critical exception caught in {loop_name}. Initiating Self-Heal diagnostic...")
    
    # Hash the error signature
    error_signature = f"{type(exception).__name__}:{str(exception)[:50]}"
    sig_hash = hashlib.md5(error_signature.encode()).hexdigest()
    
    cache = _get_cache()
    last_seen = cache.get(sig_hash, 0)
    current_time = time.time()
    
    if current_time - last_seen < COOLDOWN_SECONDS:
        print(f"[SRE] Crash signature {sig_hash} seen recently. Suppressing API call to save rate limits.")
        return "Suppressed identical recurring crash to prevent rate limiting."
        
    cache[sig_hash] = current_time
    _save_cache(cache)
    
    # Ask AI to diagnose
    system_instruction = """You are an autonomous Site Reliability Engineer (SRE) for a high-frequency trading bot called Vriddhi. 
A critical Python exception just crashed one of the event loops.
Your job is to analyze the stack trace, identify the exact bug, and provide the exact Python code patch to fix it.
Be concise, direct, and ruthless in your debugging."""

    user_prompt = f"Loop: {loop_name}\nException: {type(exception).__name__}: {str(exception)}\nTraceback:\n{tb_str}"
    
    try:
        c = get_client()
        response = await c.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
            ),
        )
        ai_diagnosis = response.text
    except Exception as e:
        print(f"[SRE] API Error during diagnostic: {e}")
        ai_diagnosis = "SRE AI offline or failed to diagnose."
        
    # Log to local JSON file
    report = {
        "timestamp": datetime.now().isoformat(),
        "loop_name": loop_name,
        "error_signature": error_signature,
        "traceback": tb_str,
        "ai_diagnosis": ai_diagnosis
    }
    
    reports = []
    if os.path.exists(REPORTS_FILE):
        try:
            with open(REPORTS_FILE, 'r') as f:
                reports = json.load(f)
        except Exception:
            pass
            
    reports.insert(0, report)
    # Keep last 20 reports
    reports = reports[:20]
    
    try:
        with open(REPORTS_FILE, 'w') as f:
            json.dump(reports, f, indent=2)
    except Exception as e:
        print(f"[SRE] Error saving anomaly report: {e}")
        
    return ai_diagnosis
