#!/bin/bash
# Deploy to Raspberry Pi (raspi50)
# Usage: ./deploy_to_pi.sh

set -e

echo "🚀 Deploying Bank Nifty Bot to Raspberry Pi..."

# Configuration
SSH_CMD="ssh -i ~/.ssh/id_ed25519_raspi -p 2222 neerajsharma@192.168.0.54"
SCP_CMD="scp -i ~/.ssh/id_ed25519_raspi -P 2222"
REMOTE_USER="neerajsharma"
REMOTE_HOST="192.168.0.54"
REMOTE_DIR="/home/neerajsharma/options-quant"
LOCAL_DIR="$(pwd)"

# Step 1: Create remote directory
echo "📁 Creating remote directory..."
$SSH_CMD "mkdir -p $REMOTE_DIR"

# Step 2: Sync project files
echo "📤 Syncing files to Raspberry Pi..."
rsync -avz --progress -e "ssh -i ~/.ssh/id_ed25519_raspi -p 2222" \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='logs/*.log' \
  --exclude='logs/*.json' \
  --exclude='data/*.txt' \
  --exclude='.bot.pid' \
  "$LOCAL_DIR/" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

# Step 3: Make scripts executable
echo "🔧 Setting permissions..."
$SSH_CMD "cd $REMOTE_DIR && chmod +x *.sh market_scheduler.sh"

# Step 4: Check if .env exists
echo "🔍 Checking .env file..."
if $SSH_CMD "test -f $REMOTE_DIR/.env"; then
    echo "✅ .env file exists on remote"
else
    echo "⚠️  WARNING: .env file not found on remote!"
    echo "   Copying .env file..."
    $SCP_CMD .env "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"
    echo "✅ .env file copied"
fi

# Step 5: Build Docker image
echo "🐳 Building Docker image on Pi..."
$SSH_CMD "cd $REMOTE_DIR && docker-compose build"

# Step 6: Setup systemd service (optional)
echo "⚙️  Setting up systemd service..."
read -p "Install systemd service for auto-start on boot? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    $SSH_CMD "sudo cp $REMOTE_DIR/trading-bot.service /etc/systemd/system/ && \
              sudo systemctl daemon-reload && \
              sudo systemctl enable trading-bot.service"
    echo "✅ Systemd service installed and enabled"
fi

# Step 7: Setup crontab for market hours
echo "⏰ Setting up market hours cron jobs..."
read -p "Install cron jobs for auto start/stop during market hours? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    $SSH_CMD "( crontab -l 2>/dev/null | grep -v 'options-quant' ; \
      echo '# Bank Nifty Bot - Market Hours' ; \
      echo '0 9 * * 1-5 $REMOTE_DIR/market_scheduler.sh start' ; \
      echo '45 15 * * 1-5 $REMOTE_DIR/market_scheduler.sh stop' ; \
      echo '35 15 * * 1-5 cd $REMOTE_DIR && docker-compose exec -T trading-bot python generate_pnl_report.py' \
    ) | crontab -"
    echo "✅ Cron jobs installed"
fi

# Step 8: Start the bot
echo ""
read -p "Start the bot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    $SSH_CMD "cd $REMOTE_DIR && docker-compose up -d"
    echo "✅ Bot started!"
    echo ""
    echo "Check status with:"
    echo "  $SSH_CMD 'cd $REMOTE_DIR && docker-compose ps'"
else
    echo "ℹ️  Bot not started. Start manually with:"
    echo "  $SSH_CMD 'cd $REMOTE_DIR && docker-compose up -d'"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Useful commands:"
echo "  $SSH_CMD 'cd $REMOTE_DIR && docker-compose logs -f'    # View logs"
echo "  $SSH_CMD 'cd $REMOTE_DIR && ./market_scheduler.sh status'  # Check status"
echo "  $SSH_CMD 'cd $REMOTE_DIR && docker-compose restart'    # Restart"
