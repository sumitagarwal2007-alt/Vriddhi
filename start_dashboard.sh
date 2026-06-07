#!/bin/bash
echo "========================================="
echo "   VRIDDHI QUANT - GOD'S EYE DASHBOARD   "
echo "========================================="
echo ""
echo "Cleaning up old sessions..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
pkill -f "cloudflared" 2>/dev/null
rm -f web.log cloudflare.log

echo "Starting Local Flask Server on Port 8000..."
nohup venv/bin/python app.py < /dev/null > web.log 2>&1 &
disown

echo "Booting up Secure Cloudflare Tunnel..."
nohup ./cloudflared tunnel --url http://localhost:8000 < /dev/null > cloudflare.log 2>&1 &
disown

echo "Waiting for Cloudflare to assign a public URL..."
sleep 4

URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' cloudflare.log | head -1)

if [ -n "$URL" ]; then
    echo ""
    echo "========================================="
    echo "✅ SECURE GLOBAL LINK GENERATED!"
    echo "You can access your dashboard from anywhere via 5G at:"
    echo -e "\033[1;32m$URL\033[0m"
    echo "========================================="
else
    echo "⚠️ Could not parse the URL automatically."
    echo "Please check cloudflare.log manually."
fi
