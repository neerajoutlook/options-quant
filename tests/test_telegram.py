#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/neerajsharma/personal/python-projects/options-quant')

from core.telegram_bot import TelegramBot

def test_telegram():
    bot = TelegramBot()
    
    print("Testing Telegram Bot...")
    
    # Test 1: Simple message
    print("\n1. Sending startup alert...")
    result1 = bot.send_message("🚀 <b>Sensex Bot Started</b>\n\nSystem initialized successfully!")
    print(f"   Result: {'✅ Success' if result1 else '❌ Failed'}")
    
    # Test 2: Trade alert
    print("\n2. Sending trade alert...")
    bot.send_trade_alert(
        symbol="SENSEX06DEC78000CE",
        signal_type="BUY",
        price=78000.50,
        reason="Weighted strength > 5.0",
        order_id="TEST123456"
    )
    
    # Test 3: Order update
    print("\n3. Sending order update...")
    result3 = bot.send_message("📊 Order Update: COMPLETE")
    print(f"   Result: {'✅ Success' if result3 else '❌ Failed'}")
    
    print("\n✅ Check your Telegram for 3 messages!")

if __name__ == "__main__":
    test_telegram()
