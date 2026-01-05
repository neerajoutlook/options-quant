# Bot Management Commands

## Start Bot
```bash
./run.sh
```
- Starts bot in background
- Saves PID to `.bot.pid` file
- Shows PID on startup

## Stop Bot
```bash
./stop.sh
```
- Gracefully stops bot using saved PID
- Force kills if needed
- Removes PID file

## Check Status
```bash
./status.sh
```
- Shows if bot is running
- Displays PID and resource usage
- Shows recent log activity

## Manual Control
```bash
# Find PID
cat .bot.pid

# Kill manually
kill $(cat .bot.pid)

# Force kill
kill -9 $(cat .bot.pid)

# Find all instances
ps aux | grep "python.*main.py" | grep -v grep
```

## Logs
```bash
# Live trading log
tail -f logs/trading.log

# Live order log
tail -f logs/orders.log

# View end-of-day summary
./view_orders.sh
```

## PID File
- Location: `.bot.pid`
- Contains: Process ID of running bot
- Auto-created by `run.sh`
- Auto-removed by `stop.sh`
