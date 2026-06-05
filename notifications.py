import os
import requests
from dotenv import load_dotenv

load_dotenv()

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_alert(title: str, description: str, color: int = 0x00FF00):
    """Dispatch an alert to Discord and/or Email depending on configuration."""
    print(f"[Alert Hub] {title} - {description}")
    
    # Discord
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if webhook_url and webhook_url != "YOUR_DISCORD_WEBHOOK_OR_BLANK":
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

    # Email
    smtp_server = os.getenv("SMTP_SERVER")
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")

    if smtp_server and sender_email and sender_password and recipient_email and sender_password != "your_app_password":
        try:
            port = int(os.getenv("SMTP_PORT", 587))
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"Vriddhi Quant Alert: {title}"
            
            body = f"{title}\n\n{description}"
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"[Alert Hub] Failed to send Email alert: {e}")
