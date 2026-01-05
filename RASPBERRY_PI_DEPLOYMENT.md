# Raspberry Pi Deployment Guide

## Prerequisites on Raspberry Pi

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker pi
sudo systemctl enable docker
sudo systemctl start docker

# Install Docker Compose
sudo apt-get install docker-compose -y

# Reboot
sudo reboot
```

## Deployment Steps

### 1. Transfer Code to Raspberry Pi

```bash
# On your Mac
cd /Users/neerajsharma/personal/python-projects
rsync -avz --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
  options-quant/ pi@<raspberry-pi-ip>:~/options-quant/
```

### 2. Setup on Raspberry Pi

```bash
# SSH into Pi
ssh pi@<raspberry-pi-ip>

# Navigate to project
cd ~/options-quant

# Make scripts executable
chmod +x market_scheduler.sh

# Copy .env file (or create it)
nano .env  # Add your credentials

# Build and start
docker-compose build
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

### 3. Setup Auto-Start on Boot

```bash
# Copy systemd service
sudo cp trading-bot.service /etc/systemd/system/

# Enable auto-start
sudo systemctl daemon-reload
sudo systemctl enable trading-bot.service

# Start now
sudo systemctl start trading-bot.service

# Check status
sudo systemctl status trading-bot.service
```

### 4. Setup Market Hours Scheduling

```bash
# Edit crontab
crontab -e

# Add these lines:
# Start at 9:00 AM on trading days (Mon-Fri)
0 9 * * 1-5 /home/pi/options-quant/market_scheduler.sh start

# Stop at 3:45 PM on trading days
45 15 * * 1-5 /home/pi/options-quant/market_scheduler.sh stop

# Generate P&L report at 3:35 PM
35 15 * * 1-5 cd /home/pi/options-quant && docker-compose exec -T trading-bot python generate_pnl_report.py

# Save and exit
```

## Management Commands

### Daily Operations

```bash
# Check status
./market_scheduler.sh status

# View logs
./market_scheduler.sh logs

# Manual start (for testing or Saturday trading)
./market_scheduler.sh force-start

# Stop bot
./market_scheduler.sh stop

# Restart bot
./market_scheduler.sh restart
```

### Docker Commands

```bash
# View logs
docker-compose logs -f

# Check container status
docker-compose ps

# Restart container
docker-compose restart

# Rebuild after code changes
docker-compose down
docker-compose build
docker-compose up -d

# Execute command in container
docker-compose exec trading-bot python generate_pnl_report.py
```

### System Management

```bash
# Check systemd status
sudo systemctl status trading-bot

# Restart systemd service
sudo systemctl restart trading-bot

# View systemd logs
sudo journalctl -u trading-bot -f

# Disable auto-start
sudo systemctl disable trading-bot
```

## Monitoring

### Check Bot Health

```bash
# Container health
docker ps

# Application logs
tail -f logs/trading.log

# Order logs
tail -f logs/orders.log

# View order summary
docker-compose exec trading-bot ./view_orders.sh
```

### System Resources

```bash
# Container stats
docker stats banknifty-bot

# Disk usage
du -sh logs/ data/

# Check memory
free -h
```

## Updating the Bot

```bash
# On Mac - push changes
cd /Users/neerajsharma/personal/python-projects/options-quant
rsync -avz --exclude='venv' --exclude='__pycache__' \
  ./ pi@<raspberry-pi-ip>:~/options-quant/

# On Pi - rebuild
cd ~/options-quant
docker-compose down
docker-compose build
docker-compose up -d
```

## Troubleshooting

### Bot Not Starting

```bash
# Check Docker
docker-compose logs

# Check systemd
sudo journalctl -u trading-bot -n 50

# Check cron logs
grep CRON /var/log/syslog
```

### WebSocket Issues

```bash
# Restart container
docker-compose restart

# Check network
ping api.shoonya.com
```

### Market Hours Not Working

```bash
# List cron jobs
crontab -l

# Check cron service
sudo systemctl status cron

# Test manual start
./market_scheduler.sh force-start
```

## Enhanced Telegram Alerts

All alerts now include:
- **PID**: Process ID
- **Time**: Exact timestamp
- **Memory**: Current memory usage
- **Host**: Hostname (raspberry-pi or your Pi's name)
- **Prices**: Entry/exit prices
- **P&L**: Calculated profit/loss

## Market Schedule (IST)

- **Pre-market**: 9:00 AM - Bot starts
- **Market open**: 9:15 AM - 3:30 PM
- **Post-market**: 3:30 PM - P&L report generated
- **Market close**: 3:45 PM - Bot stops
- **Weekends**: Bot remains off unless manually started

## Manual Override

For testing or special trading days:

```bash
# Start anytime
./market_scheduler.sh force-start

# Stop anytime
./market_scheduler.sh stop
```
