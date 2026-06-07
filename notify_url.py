import sys
from notifications import send_alert

def main():
    if len(sys.argv) < 2:
        return
    url = sys.argv[1]
    send_alert(
        "📱 God's Eye Online", 
        f"Vriddhi Dashboard is globally accessible at:\n**{url}**",
        0x66FCF1
    )

if __name__ == '__main__':
    main()
