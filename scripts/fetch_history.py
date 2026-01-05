
import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta, date
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from core.shoonya_client import ShoonyaSession
# from core.utils import get_india_time
import pytz

def get_india_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HistoryFetcher")

DATA_DIR = Path("data/history")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def fetch_banknifty_history(days=30):
    """
    Fetch last N days of BANKNIFTY Spot Data (1 Minute Intervals)
    """
    try:
        # 1. Login
        session = ShoonyaSession()
        login_res = session.login()
        if not login_res or login_res.get('stat') != 'Ok':
            logger.error("Login failed. Exiting.")
            return

        # 2. Configuration
        exchange = 'NSE'
        token = '26009' # Nifty Bank
        interval = 1 
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"Fetching data from {start_date.date()} to {end_date.date()} for {exchange}:{token}")
        
        all_candles = []
        
        # 3. Chunked Fetch (Shoonya limit is often restricted, safe to do 5 days at a time)
        chunk_days = 5
        current_start = start_date
        
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_days), end_date)
            
            logger.info(f"Downloading chunk: {current_start.date()} -> {current_end.date()}")
            
            candles = session.get_history(
                exchange=exchange,
                token=token,
                start_time=current_start.timestamp(),
                end_time=current_end.timestamp(),
                interval=interval
            )
            
            if candles:
                logger.info(f"  Received {len(candles)} candles.")
                # Filter out duplicates if overlap
                if all_candles:
                    last_ts = all_candles[-1]['ssboe']
                    new_candles = [c for c in candles if int(c['ssboe']) > int(last_ts)]
                    all_candles.extend(new_candles)
                else:
                    all_candles.extend(candles)
            else:
                logger.warning("  No data received for this chunk.")
            
            # Rate limit politeness
            time.sleep(0.5)
            current_start = current_end

        # 4. Sort and Validate
        # Shoonya 'ssboe' is seconds since epoch (as string usually)
        all_candles.sort(key=lambda x: int(x['ssboe']))
        
        logger.info(f"✅ Total Candles Fetched: {len(all_candles)}")
        if all_candles:
            logger.info(f"Range: {all_candles[0]['time']} to {all_candles[-1]['time']}")
        
        # 5. Save to JSON
        output_file = DATA_DIR / "banknifty_spot_m1.json"
        with open(output_file, 'w') as f:
            json.dump(all_candles, f, indent=None) # Compact JSON
            
        logger.info(f"💾 Saved to {output_file}")
        
    except Exception as e:
        logger.error(f"❌ Fetch failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fetch_banknifty_history(days=30)
