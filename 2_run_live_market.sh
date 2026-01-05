#!/bin/bash
# Live Market Mode - For real trading during market hours
# Uses real API data - Paper mode ON by default for safety
# Port: 8002

echo "🟢 Starting LIVE MARKET MODE..."
echo "================================================"
echo "⚠️  WARNING: LIVE MARKET DATA"
echo "⚠️  Paper Mode ON (for safety)"
echo "📍 Port: 8002"
echo "================================================"
echo ""
echo "Market Hours: Mon-Fri, 9:15 AM - 3:30 PM IST"
echo ""
echo "Before trading:"
echo "  1. Check 'Mode' toggle (Paper/Real)"
echo "  2. Check 'AI Auto Trade' toggle"
echo "  3. Verify Shoonya credentials in .env"
echo ""
echo "Dashboard: http://localhost:8002"
echo "================================================"
echo ""

# Set environment variables for live mode
export SIMULATION_MODE=False
export PAPER_TRADING_MODE=True  # Default to Paper for safety
export FORCE_LIVE_MODE=True     # Prevent auto-enabling simulation when market is closed
export WEB_PORT=8002

# Kill any existing process on port 8002
echo "🧹 Checking for existing process on port 8002..."
OLD_PID=$(lsof -ti:8002 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "⚠️  Found existing process (PID: $OLD_PID) - killing it..."
    kill -9 $OLD_PID 2>/dev/null
    sleep 1
    echo "✅ Old process killed"
fi

# Handle Ctrl+C properly
trap 'echo ""; echo "🛑 Shutting down live market..."; exit 0' SIGINT SIGTERM

# Launch the platform (exec replaces shell so signals reach Python directly)
exec python launch_web.py
