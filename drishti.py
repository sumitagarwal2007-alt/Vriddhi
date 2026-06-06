import subprocess
import sys
import os
import time
from collections import deque
from notifications import send_alert

# Make sure logs directory exists outside of iCloud (Home directory)
LOG_DIR = os.path.expanduser("~/Vriddhi_Logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Rolling buffer of last 25 lines
log_buffer = deque(maxlen=25)
LAST_ALERT_TIME = 0
ALERT_COOLDOWN = 300  # 5 minutes

def print_banner():
    banner = """
===================================================================
      [👁️] AGENT DRISHTI (WATCHDOG) ACTIVATED
===================================================================
      Monitoring main.py for fatal errors and crashes...
===================================================================
"""
    print(banner)

def main():
    global LAST_ALERT_TIME
    print_banner()
    
    log_file = open(os.path.join(LOG_DIR, "main.log"), "a")
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Agent DRISHTI] Launching core engine...")
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            
            log_file.write(line)
            log_file.flush()
            
            log_buffer.append(line.strip())
            
            # Detect soft errors
            line_lower = line.lower()
            if " error" in line_lower or "error:" in line_lower:
                current_time = time.time()
                if current_time - LAST_ALERT_TIME > ALERT_COOLDOWN:
                    error_context = "\n".join(log_buffer)
                    alert_desc = f"Agent DRISHTI detected an anomaly in the live logs:\n```\n{error_context}\n```"
                    # Fire asynchronously so we don't block reading logs
                    try:
                        send_alert("🚨 Engine Anomaly Detected", alert_desc, color=0xFFA500)
                    except:
                        pass
                    LAST_ALERT_TIME = current_time
                    
    except KeyboardInterrupt:
        print("\n[Agent DRISHTI] Received shutdown signal. Terminating engine...")
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            print("[Agent DRISHTI] Engine hung on shutdown. Force killing (SIGKILL)...")
            proc.kill()
            proc.wait()
    except Exception as e:
        print(f"\n[Agent DRISHTI] Watchdog internal error: {e}")
    finally:
        proc.wait()
        log_file.close()
        
        # Death Alert
        if proc.returncode != 0 and proc.returncode is not None and proc.returncode != -15:
            error_context = "\n".join(log_buffer)
            alert_desc = f"The main engine process CRASHED with exit code {proc.returncode}!\n\nLast trace:\n```\n{error_context}\n```"
            try:
                send_alert("💀 ENGINE CRASH DETECTED", alert_desc, color=0x8B0000)
            except:
                pass
            print("\n[Agent DRISHTI] CRASH ALERT DISPATCHED TO DISCORD.")

if __name__ == "__main__":
    main()
