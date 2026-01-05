#!/bin/bash
# Market hours scheduler - Start/stop bot based on Indian market timings
# Add to crontab: crontab -e
# Then add these lines (uncomment):

# Start bot at 9:00 AM IST on trading days (Mon-Fri)
# 0 9 * * 1-5 /home/pi/options-quant/market_scheduler.sh start

# Stop bot at 3:45 PM IST on trading days
# 45 15 * * 1-5 /home/pi/options-quant/market_scheduler.sh stop

# Optional: Generate P&L report at market close
# 35 15 * * 1-5 cd /home/pi/options-quant && docker-compose exec trading-bot python generate_pnl_report.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ACTION=${1:-status}

case "$ACTION" in
    start)
        echo "Starting trading bot for market hours..."
        docker-compose up -d
        echo "Bot started. Check status with: docker-compose ps"
        ;;
    
    stop)
        echo "Stopping trading bot (market closed)..."
        docker-compose down
        echo "Bot stopped."
        ;;
    
    restart)
        echo "Restarting trading bot..."
        docker-compose restart
        ;;
    
    status)
        echo "=== Trading Bot Status ==="
        docker-compose ps
        echo ""
        echo "=== Container Logs (last 20 lines) ==="
        docker-compose logs --tail=20
        ;;
    
    force-start)
        echo "Force starting bot (manual override)..."
        docker-compose up -d
        echo "Bot force-started."
        ;;
    
    logs)
        docker-compose logs -f
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status|force-start|logs}"
        exit 1
        ;;
esac
