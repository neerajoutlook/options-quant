import logging
import time
from datetime import datetime, timedelta
import pytz
from core.shoonya_client import ShoonyaSession
from core.config import SHOONYA_USER

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Timezone
IST = pytz.timezone('Asia/Kolkata')

def main():
    logger.info("Starting Daily History Test...")
    session = ShoonyaSession()
    try:
        session.login()
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return

    token = "1333" # HDFCBANK
    exchange = "NSE"
    
    now = datetime.now(IST)
    start_time = now - timedelta(days=30)
    
    logger.info(f"Fetching history from {start_time}...")
    
    # Try 60 minutes
    try:
        logger.info("👉 Attempting interval='60'...")
        history = session.get_history(exchange, token, start_time.timestamp(), interval="60")
        if history:
            logger.info(f"✅ Success (60)! Got {len(history)} candles.")
            logger.info(f"First: {history[0]}")
            logger.info(f"Last: {history[-1]}")
            return
        else:
            logger.warning(f"❌ Failed (60). Result: {history}")
    except Exception as e:
        logger.error(f"Error (60): {e}")

    # Try 'd'
    try:
        logger.info("👉 Attempting interval='d'...")
        history = session.get_history(exchange, token, start_time.timestamp(), interval="d")
        if history:
            logger.info(f"✅ Success ('d')! Got {len(history)} candles.")
            return
        else:
            logger.warning(f"❌ Failed ('d'). Result: {history}")
    except Exception as e:
        logger.error(f"Error ('d'): {e}")

if __name__ == "__main__":
    main()
