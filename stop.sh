#!/bin/bash
# Stop the trading bot

if [ ! -f .bot.pid ]; then
    echo "❌ No PID file found. Bot may not be running."
    echo "Checking for running instances..."
    ps aux | grep "python.*main.py" | grep -v grep
    exit 1
fi

PID=$(cat .bot.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping bot (PID: $PID)..."
    kill $PID
    sleep 1
    
    # Force kill if still running
    if ps -p $PID > /dev/null 2>&1; then
        echo "Force killing bot..."
        kill -9 $PID
    fi
    
    rm .bot.pid
    echo "✅ Bot stopped"
else
    echo "❌ Bot with PID $PID is not running"
    rm .bot.pid
fi
