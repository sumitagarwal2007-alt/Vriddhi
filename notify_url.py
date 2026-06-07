import sys
from discord_notifier import DiscordNotifier

def main():
    if len(sys.argv) < 2:
        return
    url = sys.argv[1]
    notif = DiscordNotifier()
    notif.send_alert(
        "📱 God's Eye Online", 
        f"Vriddhi Dashboard is globally accessible at:\n**{url}**",
        0x66FCF1
    )

if __name__ == '__main__':
    main()
