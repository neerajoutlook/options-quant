import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Shoonya Credentials
SHOONYA_USER = os.getenv("SHOONYA_USER")
SHOONYA_PWD = os.getenv("SHOONYA_PWD")
SHOONYA_API_KEY = os.getenv("SHOONYA_API_KEY")
SHOONYA_TOTP = os.getenv("SHOONYA_TOTP")
SHOONYA_VENDOR = os.getenv("SHOONYA_VENDOR")
SHOONYA_IMEI = os.getenv("SHOONYA_IMEI", "abc1234")

# Telegram Credentials
TELEGRAM_BOT_TOKEN = os.getenv("MAA_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("MAA_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

# Trading Config
TRADING_SYMBOL_CE = os.getenv("TRADING_SYMBOL_CE")
TRADING_SYMBOL_PE = os.getenv("TRADING_SYMBOL_PE")
QUANTITY = 20 # Lot size
USE_VOLUME_WEIGHTING = False # Experimental: Use volume in strength calculation

# Paper Trading
PAPER_TRADING_MODE = os.getenv("PAPER_TRADING_MODE", "true").lower() == "true"  # Default: paper trading ON

# Signal Quality Filters (for high conviction trades)
MIN_SIGNAL_STRENGTH = float(os.getenv("MIN_SIGNAL_STRENGTH", "5.5"))  # Minimum strength to generate signal (higher = fewer, better signals)
MIN_SIGNAL_HOLD_TIME = int(os.getenv("MIN_SIGNAL_HOLD_TIME", "60"))  # Seconds to hold before allowing new signal (prevents churn)
