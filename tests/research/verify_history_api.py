
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.shoonya_client import ShoonyaSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_history_fetch():
    try:
        # 1. Login
        session = ShoonyaSession()
        session.login()
        
        # 2. Get Token for BANKNIFTY Index
        # Usually Nifty Bank token is '26009' on NSE or NFO? 
        # Exchange: NSE, Token: 26009 (Nifty Bank)
        exchange = 'NSE'
        token = '26009' 
        
        logger.info(f"Fetching 5 days history for {exchange}:{token}...")
        
        end = datetime.now()
        start = end - timedelta(days=5)
        
        history = session.get_history(
            exchange=exchange, 
            token=token, 
            start_time=start.timestamp(), 
            end_time=end.timestamp(), 
            interval=1 # 1 Minute
        )
        
        if history:
            logger.info(f"✅ Success! Received {len(history)} candles.")
            logger.info(f"First Candle: {history[0]}")
            logger.info(f"Last Candle: {history[-1]}")
        else:
            logger.error("❌ No history data returned (None).")
            
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")

if __name__ == "__main__":
    test_history_fetch()
