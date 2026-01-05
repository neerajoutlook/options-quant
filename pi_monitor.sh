#!/bin/bash
# Remote monitoring script for Raspberry Pi trading bot
# Usage: ./pi_monitor.sh [command]

SSH_CMD="ssh -i ~/.ssh/id_ed25519_raspi -p 2222 neerajsharma@100.76.123.9"
REMOTE_DIR="/home/neerajsharma/options-quant"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_menu() {
    echo ""
    echo -e "${BLUE}=== Raspberry Pi Trading Bot Monitor ===${NC}"
    echo ""
    echo "1.  Status        - Bot & container status"
    echo "2.  Logs (live)   - Live trading logs"
    echo "3.  Logs (tail)   - Last 50 lines of trading log"
    echo "4.  Orders        - Order log (last 20)"
    echo "5.  Trades        - Today's trades"
    echo "6.  P&L Report    - Generate P&L report"
    echo "7.  Signals       - Recent signals (last 10)"
    echo "8.  Candles       - Recent candle closes"
    echo "9.  Container     - Docker container info"
    echo "10. System        - Raspberry Pi system info"
    echo "11. Restart       - Restart the bot"
    echo "12. Stop          - Stop the bot"
    echo "13. Start         - Start the bot"
    echo "14. All Logs      - Download all logs to Mac"
    echo "0.  Exit"
    echo ""
}

# Function to execute remote command
remote_exec() {
    $SSH_CMD "cd $REMOTE_DIR && $1"
}

# 1. Status
show_status() {
    echo -e "${GREEN}=== Bot Status ===${NC}"
    remote_exec "docker-compose ps"
    echo ""
    echo -e "${GREEN}=== Recent Activity ===${NC}"
    remote_exec "docker-compose logs --tail=5"
}

# 2. Live logs
show_logs_live() {
    echo -e "${GREEN}=== Live Trading Logs (Ctrl+C to exit) ===${NC}"
    remote_exec "docker-compose logs -f"
}

# 3. Tail logs
show_logs_tail() {
    echo -e "${GREEN}=== Last 50 Lines ===${NC}"
    remote_exec "docker-compose logs --tail=50"
}

# 4. Orders
show_orders() {
    echo -e "${GREEN}=== Order Log (Last 20 events) ===${NC}"
    remote_exec "tail -20 logs/orders.log 2>/dev/null || echo 'No orders yet'"
}

# 5. Trades
show_trades() {
    echo -e "${GREEN}=== Today's Trades ===${NC}"
    remote_exec "docker-compose exec -T trading-bot python -c \"
from core.position_tracker import PositionTracker
tracker = PositionTracker()
pnl_data = tracker.get_daily_pnl()
print(f'Date: {pnl_data[\"date\"]}')
print(f'Total Trades: {pnl_data[\"total_trades\"]}')
print(f'Winning: {pnl_data[\"winning_trades\"]}')
print(f'Losing: {pnl_data[\"losing_trades\"]}')
print(f'Win Rate: {pnl_data[\"win_rate\"]:.1f}%')
print(f'Gross P&L: ₹{pnl_data[\"gross_pnl\"]:.2f}')
\" 2>/dev/null || echo 'Bot not running or no trades yet'"
}

# 6. P&L Report
show_pnl_report() {
    echo -e "${GREEN}=== Generating P&L Report ===${NC}"
    remote_exec "docker-compose exec -T trading-bot python generate_pnl_report.py 2>/dev/null || echo 'Bot not running'"
}

# 7. Signals
show_signals() {
    echo -e "${GREEN}=== Recent Signals ===${NC}"
    remote_exec "grep 'SIGNAL GENERATED' logs/trading.log 2>/dev/null | tail -10 || echo 'No signals yet'"
}

# 8. Candles
show_candles() {
    echo -e "${GREEN}=== Recent Candle Closes ===${NC}"
    remote_exec "grep 'Candle Closed' logs/trading.log 2>/dev/null | tail -10 || echo 'No candles yet'"
}

# 9. Container info
show_container() {
    echo -e "${GREEN}=== Docker Container Info ===${NC}"
    remote_exec "docker stats banknifty-bot --no-stream"
    echo ""
    remote_exec "docker inspect banknifty-bot --format='{{.State.Status}}: {{.State.Health.Status}}' 2>/dev/null || echo 'Container not found'"
}

# 10. System info
show_system() {
    echo -e "${GREEN}=== Raspberry Pi System Info ===${NC}"
    $SSH_CMD "
    echo 'Hostname:' \$(hostname)
    echo 'Uptime:' \$(uptime -p)
    echo 'Memory:' \$(free -h | grep Mem | awk '{print \$3\"/\"\$2}')
    echo 'Disk:' \$(df -h / | tail -1 | awk '{print \$3\"/\"\$2 \" (\" \$5 \" used)\"}'  )
    echo 'CPU Temp:' \$(vcgencmd measure_temp 2>/dev/null || echo 'N/A')
    "
}

# 11. Restart
restart_bot() {
    echo -e "${YELLOW}=== Restarting Bot ===${NC}"
    remote_exec "docker-compose restart"
    echo -e "${GREEN}✅ Bot restarted${NC}"
}

# 12. Stop
stop_bot() {
    echo -e "${RED}=== Stopping Bot ===${NC}"
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        remote_exec "docker-compose down"
        echo -e "${GREEN}✅ Bot stopped${NC}"
    fi
}

# 13. Start
start_bot() {
    echo -e "${GREEN}=== Starting Bot ===${NC}"
    remote_exec "docker-compose up -d"
    echo -e "${GREEN}✅ Bot started${NC}"
}

# 14. Download all logs
download_logs() {
    echo -e "${GREEN}=== Downloading Logs ===${NC}"
    mkdir -p ./pi_logs
    scp -i ~/.ssh/id_ed25519_raspi -P 2222 \
        neerajsharma@192.168.0.54:$REMOTE_DIR/logs/*.log \
        ./pi_logs/ 2>/dev/null
    scp -i ~/.ssh/id_ed25519_raspi -P 2222 \
        neerajsharma@192.168.0.54:$REMOTE_DIR/logs/*.json \
        ./pi_logs/ 2>/dev/null
    echo -e "${GREEN}✅ Logs downloaded to ./pi_logs/${NC}"
    ls -lh ./pi_logs/
}

# Main script
case "$1" in
    status|1)
        show_status
        ;;
    logs-live|2)
        show_logs_live
        ;;
    logs-tail|logs|3)
        show_logs_tail
        ;;
    orders|4)
        show_orders
        ;;
    trades|5)
        show_trades
        ;;
    pnl|6)
        show_pnl_report
        ;;
    signals|7)
        show_signals
        ;;
    candles|8)
        show_candles
        ;;
    container|9)
        show_container
        ;;
    system|10)
        show_system
        ;;
    restart|11)
        restart_bot
        ;;
    stop|12)
        stop_bot
        ;;
    start|13)
        start_bot
        ;;
    download|14)
        download_logs
        ;;
    *)
        # Interactive menu
        while true; do
            show_menu
            read -p "Select option: " choice
            case $choice in
                1) show_status ;;
                2) show_logs_live ;;
                3) show_logs_tail ;;
                4) show_orders ;;
                5) show_trades ;;
                6) show_pnl_report ;;
                7) show_signals ;;
                8) show_candles ;;
                9) show_container ;;
                10) show_system ;;
                11) restart_bot ;;
                12) stop_bot ;;
                13) start_bot ;;
                14) download_logs ;;
                0) echo "Goodbye!"; exit 0 ;;
                *) echo -e "${RED}Invalid option${NC}" ;;
            esac
            
            if [ "$choice" != "2" ]; then
                read -p "Press Enter to continue..."
            fi
        done
        ;;
esac
