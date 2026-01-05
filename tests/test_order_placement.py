#!/usr/bin/env python3
"""
Test script to verify order placement functionality
Places small test orders that user will manually cancel
"""
import sys
sys.path.insert(0, '/Users/neerajsharma/personal/python-projects/options-quant')

from core.shoonya_client import ShoonyaSession
from core.telegram_bot import TelegramBot
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_order_placement():
    """Test order placement with SBIN equity and Bank Nifty options"""
    
    session = ShoonyaSession()
    telegram = TelegramBot()
    
    # Login
    logger.info("Logging in to Shoonya...")
    session.login()
    telegram.send_message("🧪 **Order Placement Test Started**")
    
    # Test 1: Place SBIN equity order (1 quantity)
    logger.info("\n=== Test 1: SBIN Equity Order ===")
    try:
        order_id = session.place_order(
            buy_or_sell="B",
            product_type="C",  # CNC for delivery
            exchange="NSE",
            tradingsymbol="SBIN-EQ",
            quantity=1,
            discloseqty=0,
            price_type="MKT",
            price=0,
            trigger_price=None,
            retention="DAY",
            remarks="Test-SBIN"
        )
        
        if order_id:
            msg = f"✅ **SBIN Order Placed**\nOrder ID: {order_id}\nQuantity: 1\nType: Market\n\n⚠️ Please cancel manually!"
            logger.info(f"SBIN order placed: {order_id}")
            telegram.send_message(msg)
        else:
            msg = "❌ SBIN order failed"
            logger.error(msg)
            telegram.send_message(msg)
    except Exception as e:
        msg = f"❌ SBIN Exception: {e}"
        logger.error(msg)
        telegram.send_message(msg)
    
    # Test 2: Place Bank Nifty ATM CE option order (20 qty = 1 lot)
    logger.info("\n=== Test 2: Bank Nifty ATM CE Option ===")
    
    # Get current Bank Nifty price (approximate from market)
    # For testing, using ~51500 as approximate ATM
    # You should replace this with actual current price
    current_price = 51500  # Replace with actual Bank Nifty price
    strike = round(current_price / 100) * 100
    
    # Calculate next Wednesday expiry
    today = datetime.now()
    days_until_wednesday = (2 - today.weekday()) % 7
    if days_until_wednesday == 0 and today.hour >= 15:
        days_until_wednesday = 7
    expiry_date = today + timedelta(days=days_until_wednesday)
    expiry_str = expiry_date.strftime("%d%b").upper()
    
    # Construct option symbol
    symbol = f"BANKNIFTY{expiry_str}{strike}CE"
    
    logger.info(f"Attempting to place order for: {symbol}")
    
    try:
        order_id = session.place_order(
            buy_or_sell="B",
            product_type="M",  # MIS for intraday
            exchange="NFO",
            tradingsymbol=symbol,
            quantity=20,  # 1 lot
            discloseqty=0,
            price_type="MKT",
            price=0,
            trigger_price=None,
            retention="DAY",
            remarks="Test-BANKNIFTY"
        )
        
        if order_id:
            msg = f"✅ **Bank Nifty Option Order Placed**\nSymbol: {symbol}\nOrder ID: {order_id}\nQuantity: 20 (1 lot)\nType: Market\n\n⚠️ Please cancel manually!"
            logger.info(f"Bank Nifty order placed: {order_id}")
            telegram.send_message(msg)
        else:
            msg = f"❌ Bank Nifty order failed for {symbol}"
            logger.error(msg)
            telegram.send_message(msg)
    except Exception as e:
        msg = f"❌ Bank Nifty Exception: {e}"
        logger.error(msg)
        telegram.send_message(msg)
    
    telegram.send_message("🧪 **Order Placement Test Complete**\n\n⚠️ Remember to cancel test orders!")
    logger.info("\n=== Test Complete ===")
    logger.info("Please cancel test orders from your Shoonya terminal")

if __name__ == "__main__":
    test_order_placement()
