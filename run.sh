#!/bin/bash
# Run the trading bot in background and save PID

python main.py &
echo $! > .bot.pid
echo "Bot started with PID: $(cat .bot.pid)"
echo "Stop with: ./stop.sh or kill $(cat .bot.pid)"
