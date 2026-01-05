import requests
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        # Try MAA_ prefix first (user's convention), then fall back to standard names
        self.token = os.getenv("MAA_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("MAA_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        if not self.token or not self.chat_id:
            logger.warning("⚠️ Telegram credentials not found. Alerts will be disabled.")

    def send_message(self, message: str) -> bool:
        """Send a text message to the configured chat ID."""
        if not self.token or not self.chat_id:
            return False
            
        try:
            url = f"{self.base_url}/sendMessage"
            
            # Clean message: remove Markdown formatting that doesn't work in plain text
            clean_msg = message.replace("**", "").replace("`", "")
            
            payload = {
                "chat_id": self.chat_id,
                "text": clean_msg,
                # No parse_mode - send as plain text to avoid parsing errors
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            # Log the response body for debugging
            logger.error(f"❌ Telegram HTTP Error: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            return False
    
    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters for Telegram."""
        # Telegram MarkdownV2 special characters that need escaping
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def send_trade_alert(self, symbol: str, signal_type: str, price: float, reason: str, order_id: Optional[str] = None):
        """Send a formatted trade alert."""
        emoji = "🟢" if signal_type == "BUY" else "🔴"
        msg = (
            f"{emoji} <b>TRADE ALERT: {signal_type}</b>\n\n"
            f"📌 <b>Symbol:</b> <code>{symbol}</code>\n"
            f"💰 <b>Price:</b> ₹{price:.2f}\n"
            f"📝 <b>Reason:</b> {reason}\n"
        )
        if order_id:
            msg += f"🆔 <b>Order ID:</b> <code>{order_id}</code>"
            
        self.send_message(msg)
