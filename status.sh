#!/bin/bash
# Check bot status

if [ ! -f .bot.pid ]; then
    echo "❌ No PID file found"
    echo ""
    echo "Checking for any running instances:"
    ps aux | grep "python.*main.py" | grep -v grep || echo "No bot running"
    exit 1
fi

PID=$(cat .bot.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "✅ Bot is RUNNING"
    echo "PID: $PID"
    echo ""
    ps -p $PID -o pid,ppid,%cpu,%mem,etime,command
    echo ""
    echo "Recent activity:"
    tail -5 logs/trading.log 2>/dev/null || echo "No logs yet"
else
    echo "❌ Bot is NOT running (stale PID file)"
    echo "Removing stale PID file..."
    rm .bot.pid
fi
