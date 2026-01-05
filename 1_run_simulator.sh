#!/bin/bash
# Simulator Mode - For testing and off-market hours
# Auto-enables: Simulation ON, Auto-Trade ON, Paper Mode ON
# Port: 8001

echo "🎮 Starting SIMULATOR MODE..."
echo "================================================"
echo "✅ Simulation: ON (Historical replay)"
echo "✅ Auto-Trade: ON (Automatic trading)"
echo "✅ Paper Mode: ON (No real money)"
echo "📍 Port: 8001"
echo "================================================"
echo ""
echo "Perfect for:"
echo "  - Testing strategies"
echo "  - Learning the system"
echo "  - Off-market hours practice"
echo ""
echo "Dashboard: http://localhost:8001"
echo "================================================"
echo ""

# Set environment variables for this session
export SIMULATION_MODE=True
export PAPER_TRADING_MODE=True
export WEB_PORT=8001

# Kill any existing process on port 8001
echo "🧹 Checking for existing process on port 8001..."
OLD_PID=$(lsof -ti:8001 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "⚠️  Found existing process (PID: $OLD_PID) - killing it..."
    kill -9 $OLD_PID 2>/dev/null
    sleep 1
    echo "✅ Old process killed"
fi

# Handle Ctrl+C properly
trap 'echo ""; echo "🛑 Shutting down simulator..."; exit 0' SIGINT SIGTERM

# Launch the platform (exec replaces shell so signals reach Python directly)
exec python launch_web.py
