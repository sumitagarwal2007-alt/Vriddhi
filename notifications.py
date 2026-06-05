import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_discord_alert(title: str, description: str, color: int = 0x00FF00):
    """Dispatch an alert to a Discord webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_OR_BLANK":
        print(f"[Alert Hub] {title} - {description}")
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color
            }
        ]
    }
    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"[Alert Hub] Failed to send Discord alert: {e}")
