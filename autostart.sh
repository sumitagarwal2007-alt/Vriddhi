#!/bin/bash

# =========================================
# VRIDDHI QUANT - MASTER AUTO-START SCRIPT
# =========================================

# 1. Wait for Mac to establish WiFi/Internet connection after a reboot
echo "System booting. Waiting 30 seconds for network to stabilize..."
sleep 30

# 2. Navigate to the absolute path of the project directory
cd /Users/sumitagarwal/Documents/AntiGravity/Vriddhi || exit 1

# 3. Clean up any zombie processes from an improper shutdown
echo "Cleaning up zombie ports and processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
pkill -9 -f "cloudflared" 2>/dev/null
pkill -9 -f "drishti.py" 2>/dev/null
pkill -9 -f "main.py" 2>/dev/null
pkill -9 -f "app.py" 2>/dev/null

# 4. Boot the Core Trading Engine (Drishti / Main)
echo "Booting Core Engine (Agent Drishti)..."
nohup venv/bin/python drishti.py < /dev/null > ~/Vriddhi_Logs/main.log 2>&1 &

# 5. Boot the Mobile Web Dashboard & Cloudflare Tunnel
echo "Booting God's Eye Dashboard & Secure Tunnel..."
nohup ./start_dashboard.sh < /dev/null > /dev/null 2>&1 &

echo "========================================="
echo "VRIDDHI BOOT SEQUENCE COMPLETE."
echo "Check Discord for the live Dashboard URL."
echo "========================================="
