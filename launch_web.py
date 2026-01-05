#!/usr/bin/env python3
"""
Launch script for HFT Web Platform with REAL market data
Runs both the trading bot and FastAPI web server with proper async handling
"""
import sys
import asyncio
import uvicorn
import threading
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_trading_bot():
    """Run the trading bot in a separate thread"""
    logger.info("Starting trading bot with real Shoonya connection...")
    try:
        from main import main as trading_bot_main
        trading_bot_main()
    except Exception as e:
        logger.error(f"Trading bot error: {e}", exc_info=True)

def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("HFT Web Trading Platform - REAL DATA")
    logger.info("=" * 60)
    logger.info("🌐 Dashboard: http://localhost:8000")
    logger.info("📊 Real-time data from Shoonya")
    logger.info("=" * 60)
    
    # Start trading bot in background thread
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True, name="TradingBot")
    bot_thread.start()
    
    # Give bot time to initialize
    import time
    time.sleep(2)
    
    # Auto-open browser
    import webbrowser
    try:
        webbrowser.open("http://localhost:8000")
        logger.info("🚀 Opened browser at http://localhost:8000")
    except Exception as e:
        logger.warning(f"Could not open browser: {e}")

    # Import and run web server
    from api.main import app
    
    logger.info("Starting FastAPI web server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        sys.exit(0)
