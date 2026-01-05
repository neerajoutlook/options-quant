#!/usr/bin/env python3
"""
End of day P&L report generator
Calculates and sends daily trading summary to Telegram
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.position_tracker import PositionTracker
from core.telegram_bot import TelegramBot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_pnl_report():
    """Generate and send end-of-day P&L report"""
    tracker = PositionTracker()
    telegram = TelegramBot()
    
    pnl_data = tracker.get_daily_pnl()
    
    # Format message
    emoji = "💚" if pnl_data['gross_pnl'] > 0 else "❌" if pnl_data['gross_pnl'] < 0 else "⚪"
    
    message = f"""
{emoji} **END OF DAY P&L REPORT**
📅 Date: {pnl_data['date']}

📊 **Summary**
Total Trades: {pnl_data['total_trades']}
Winning: {pnl_data['winning_trades']} ✅
Losing: {pnl_data['losing_trades']} ❌
Win Rate: {pnl_data['win_rate']:.1f}%

💰 **Gross P&L: ₹{pnl_data['gross_pnl']:.2f}**
"""
    
    if pnl_data['trades']:
        message += "\n📋 **Trade Details:**\n"
        for i, trade in enumerate(pnl_data['trades'], 1):
            pnl = trade['pnl'] or 0
            emoji_trade = "✅" if pnl > 0 else "❌"
            message += (
                f"\n{i}. {emoji_trade} {trade['symbol']}\n"
                f"   Entry: ₹{trade['entry_price']:.2f} → Exit: ₹{trade['exit_price']:.2f}\n"
                f"   P&L: ₹{pnl:.2f}"
            )
    else:
        message += "\nNo trades completed today."
    
    # Send to Telegram
    telegram.send_message(message)
    logger.info(f"P&L Report sent: {pnl_data['gross_pnl']:.2f}")
    
    print(message)
    return pnl_data

if __name__ == "__main__":
    generate_pnl_report()
