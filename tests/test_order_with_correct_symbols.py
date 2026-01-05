#!/usr/bin/env python3
"""
Comprehensive test for order placement with correct Bank Nifty symbol format
Tests SBIN equity and Bank Nifty monthly expiry options
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.shoonya_client import ShoonyaSession
from core.telegram_bot import TelegramBot
from datetime import datetime
import calendar
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_banknifty_monthly_expiry():
    """Calculate Bank Nifty monthly expiry (last Wednesday of month)"""
    today = datetime.now()
    year = today.year
    month = today.month
    
    # Find last Wednesday of current month
    last_day = calendar.monthrange(year, month)[1]
    
    expiry_date = None
    for day in range(last_day, 0, -1):
        date = datetime(year, month, day)
        if date.weekday() == 2:  # Wednesday is 2
            expiry_date = date
            break
    
    # If today is after monthly expiry, get next month's expiry
    if today > expiry_date or (today.date() == expiry_date.date() and today.hour >= 15):
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        
        last_day = calendar.monthrange(year, month)[1]
        for day in range(last_day, 0, -1):
            date = datetime(year, month, day)
            if date.weekday() == 2:
                expiry_date = date
                break
    
    return expiry_date

def test_order_placement():
    """Test order placement with correct symbol formats"""
    
    session = ShoonyaSession()
    telegram = TelegramBot()
    
    logger.info("=== Login ===")
    session.login()
    telegram.send_message("🧪 **Order Placement Test (With Correct Symbols)**")
    
    # Calculate expiry and strike
    expiry_date = get_banknifty_monthly_expiry()
    expiry_str = expiry_date.strftime("%d%b%y").upper()
    
    # Use approximate ATM strike (you should get real Bank Nifty price)
    current_price = 51500  # Approximate - replace with actual
    strike = round(current_price / 100) * 100
    
    # Construct symbol (C for Call, P for Put - NOT CE/PE!)
    symbol_ce = f"BANKNIFTY{expiry_str}C{strike}"
    symbol_pe = f"BANKNIFTY{expiry_str}P{strike}"
    
    logger.info(f"\n=== Bank Nifty Info ===")
    logger.info(f"Expiry Date: {expiry_date.strftime('%d-%b-%Y')}")
    logger.info(f"ATM Strike: {strike}")
    logger.info(f"CE Symbol: {symbol_ce}")
    logger.info(f"PE Symbol: {symbol_pe}")
    
    telegram.send_message(
        f"📊 **Bank Nifty Info**\n"
        f"Expiry: {expiry_date.strftime('%d-%b-%Y')}\n"
        f"Strike: {strike}\n"
        f"CE Symbol: `{symbol_ce}`\n"
        f"PE Symbol: `{symbol_pe}`"
    )
    
    # Test 1: SBIN Equity
    logger.info("\n=== Test 1: SBIN Equity (1 qty) ===")
    try:
        order_id = session.place_order(
            buy_or_sell="B",
            product_type="C",
            exchange="NSE",
            tradingsymbol="SBIN-EQ",
            quantity=1,
            discloseqty=0,
            price_type="MKT",
            price=0,
            retention="DAY",
            remarks="Test-SBIN"
        )
        
        if order_id:
            msg = f"✅ SBIN Order: {order_id}"
            logger.info(msg)
            telegram.send_message(f"{msg}\n⚠️ Will be rejected (no margin)")
        else:
            logger.error("SBIN order failed")
            telegram.send_message("❌ SBIN order failed")
    except Exception as e:
        logger.error(f"SBIN Exception: {e}")
        telegram.send_message(f"❌ SBIN Ex: {e}")
    
    # Test 2: Bank Nifty CE Option
    logger.info(f"\n=== Test 2: Bank Nifty CE ({symbol_ce}) ===")
    try:
        order_id = session.place_order(
            buy_or_sell="B",
            product_type="M",
            exchange="NFO",
            tradingsymbol=symbol_ce,
            quantity=20,
            discloseqty=0,
            price_type="MKT",
            price=0,
            retention="DAY",
            remarks="Test-BNCE"
        )
        
        if order_id:
            msg = f"✅ Bank Nifty CE Order: {order_id}"
            logger.info(msg)
            telegram.send_message(f"{msg}\n⚠️ Will be rejected (no margin)")
        else:
            logger.error("Bank Nifty CE order failed")
            telegram.send_message(f"❌ BN CE failed for {symbol_ce}")
    except Exception as e:
        logger.error(f"Bank Nifty CE Exception: {e}")
        telegram.send_message(f"❌ BN CE Ex: {e}")
    
    telegram.send_message("🧪 **Test Complete**\n\nCheck Shoonya for rejected orders")
    logger.info("\n=== Test Complete ===")

if __name__ == "__main__":
    test_order_placement()
