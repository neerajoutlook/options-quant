#!/usr/bin/env python3
"""
Generate paper trading P&L report
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.paper_trading import PaperTradingEngine
from core.telegram_bot import TelegramBot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_paper_pnl():
    """Generate and send paper trading P&L report"""
    paper_engine = PaperTradingEngine()
    telegram = TelegramBot()
    
    pnl_data = paper_engine.get_daily_pnl()
    
    # Format message
    emoji = "💚" if pnl_data['gross_pnl'] > 0 else "❌" if pnl_data['gross_pnl'] < 0 else "⚪"
    
    message = f"""
📝 PAPER TRADING P&L REPORT

📅 Date: {pnl_data['date']}

📊 Summary
Total Trades: {pnl_data['total_trades']}
Winning: {pnl_data['winning_trades']} ✅
Losing: {pnl_data['losing_trades']} ❌
Win Rate: {pnl_data['win_rate']:.1f}%

💰 Gross P&L: ₹{pnl_data['gross_pnl']:.2f} {emoji}
"""
    
    if pnl_data['trades']:
        message += "\n📋 Trade Details:\n"
        for i, trade in enumerate(pnl_data['trades'], 1):
            pnl = trade.get('pnl', 0) or 0
            emoji_trade = "✅" if pnl > 0 else "❌"
            message += (
                f"\n{i}. {emoji_trade} {trade['option_type']} {trade['entry_strike']}\n"
                f"   Entry: ₹{trade['entry_price']:.2f} → Exit: ₹{trade.get('exit_price', 0):.2f}\n"
                f"   P&L: ₹{pnl:.2f}"
            )
    else:
        message += "\nNo trades completed today."
    
    # Send to Telegram
    telegram.send_message(message)
    logger.info(f"Paper Trading P&L Report sent: {pnl_data['gross_pnl']:.2f}")
    
    print(message)
    return pnl_data

if __name__ == "__main__":
    generate_paper_pnl()
