import logging
import sys
from core.feed import TickEngine
from core.telegram_bot import TelegramBot
from pathlib import Path
import os
import psutil
from datetime import datetime

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/trading.log")
    ]
)

logger = logging.getLogger(__name__)

# Global instance for API access
active_engine = None

def main():
    telegram = TelegramBot()
    
    # Get system info
    pid = os.getpid()
    process = psutil.Process(pid)
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    # Startup message with system info
    startup_msg = (
        f"🚀 **Bot STARTED**\n"
        f"PID: `{pid}`\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Memory: {memory_mb:.1f} MB\n"
        f"Host: {os.uname().nodename}"
    )
    
    telegram.send_message(startup_msg)
    
    telegram.send_message(startup_msg)
    
    global active_engine
    active_engine = TickEngine()
    engine = active_engine
    
    try:
        engine.initialize()
        telegram.send_message("✅ <b>Bot Ready</b>\n\nConnecting to live feed...")
        engine.start()
        
        # Keep running - TickEngine.start is non-blocking
        import time
        logger.info("Engine running... Press Ctrl+C to stop.")
        while engine.running:
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        telegram.send_message("⏹️ <b>Bot STOPPED</b>\n\nShutdown by user")
    except Exception as e:
        logger.exception(f"Fatal Error: {e}")
        telegram.send_message(f"❌ <b>Bot CRASHED</b>\n\nError: {e}")
    finally:
        engine.stop()
        telegram.send_message("💤 <b>Bot Offline</b>")

if __name__ == "__main__":
    main()
