#!/usr/bin/env python3
"""
Final test with correct December 2025 Bank Nifty expiry
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.shoonya_client import ShoonyaSession
from core.telegram_bot import TelegramBot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_banknifty_order():
    session = ShoonyaSession()
    telegram = TelegramBot()
    
    session.login()
    
    # December 30, 2025 expiry (current month)
    # ATM strike around 51500
    strike = 51500
    symbol = f"BANKNIFTY30DEC25C{strike}"
    
    logger.info(f"Testing Bank Nifty option order: {symbol}")
    telegram.send_message(f"🧪 **Testing Order**\nSymbol: `{symbol}`")
    
    try:
        order_id = session.place_order(
            buy_or_sell="B",
            product_type="M",  # MIS
            exchange="NFO",
            tradingsymbol=symbol,
            quantity=20,
            discloseqty=0,
            price_type="MKT",
            price=0,
            retention="DAY",
            remarks="Test-BN"
        )
        
        if order_id:
            msg = f"✅ **Order Placed!**\nOrder ID: {order_id}\nSymbol: {symbol}\n\n⚠️ Will be rejected (no margin)"
            logger.info(f"SUCCESS! Order ID: {order_id}")
            telegram.send_message(msg)
        else:
            msg = f"❌ Order failed for {symbol}"
            logger.error(msg)
            telegram.send_message(msg)
    except Exception as e:
        msg = f"❌ Exception: {e}"
        logger.error(msg)
        telegram.send_message(msg)

if __name__ == "__main__":
    test_banknifty_order()
