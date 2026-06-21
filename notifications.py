import os
import requests
from dotenv import load_dotenv

load_dotenv()

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_alert(title: str, description: str, color: int = 0x00FF00, fields: dict = None):
    """Dispatch a rich alert to Discord and/or Email."""
    disclaimer = "\n\n---\n*LEGAL DISCLAIMER: This application is a paper-trading simulation and game. No actual capital is being traded. Do NOT use these signals for actual financial decisions.*"
    
    # Also replace any '$' with 'Demo $' in description and title
    description = description.replace('$', 'Demo $')
    title = title.replace('$', 'Demo $')
    
    print(f"[Alert Hub] {title} - {description}")
    
    # Discord
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if webhook_url and webhook_url != "YOUR_DISCORD_WEBHOOK_OR_BLANK":
        embed = {
            "title": title,
            "description": description + disclaimer,
            "color": color,
            "footer": {"text": "Vriddhi Quant Terminal • Institutional Engine"}
        }
        
        if fields:
            embed["fields"] = [{"name": str(k).replace('$', 'Demo $'), "value": str(v).replace('$', 'Demo $'), "inline": True} for k, v in fields.items()]
            
        payload = {"embeds": [embed]}
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
            msg = MIMEMultipart('alternative')
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"Vriddhi Quant Alert: {title}"
            
            # Plain text fallback
            text_body = f"{title}\n\n{description}"
            if fields:
                for k, v in fields.items():
                    text_body += f"\n{k}: {v}"
            text_body += disclaimer
            
            # HTML Body
            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background-color: #060913; color: #ffffff; padding: 20px;">
                <h2 style="color: #{hex(color)[2:].zfill(6)};">{title}</h2>
                <p style="font-size: 14px; line-height: 1.5; color: #e2e8f0;">{description}</p>
            """
            if fields:
                html_body += "<table style='width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #0f172a; border-radius: 8px;'>"
                for k, v in fields.items():
                    html_body += f"<tr><td style='padding: 10px; border-bottom: 1px solid #1e293b; color: #94a3b8;'><strong>{k}</strong></td><td style='padding: 10px; border-bottom: 1px solid #1e293b; color: #f8fafc;'>{v}</td></tr>"
                html_body += "</table>"
                
            html_body += f"<p style='font-size: 10px; color: #64748b; margin-top: 30px;'>{disclaimer.replace(chr(10), '<br>')}</p></body></html>"

            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"[Alert Hub] Failed to send Email alert: {e}")
