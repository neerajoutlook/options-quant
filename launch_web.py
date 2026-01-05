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
    import os
    
    # Get port from environment (default 8001)
    web_port = int(os.environ.get('WEB_PORT', '8001'))
    
    logger.info("=" * 60)
    logger.info("HFT Web Trading Platform")
    logger.info("=" * 60)
    logger.info(f"🌐 Dashboard: http://localhost:{web_port}")
    logger.info("📊 Real-time data from Shoonya")
    logger.info("=" * 60)
    
    # Smart market hours detection
    from core.market_hours import get_market_status, should_auto_enable_simulation
    from core import config
    from core.database import db
    
    market_status = get_market_status()
    logger.info(f"📅 Market Status: {market_status['reason']}")
    
    # Check if force live mode is enabled (from 2_run_live_market.sh)
    force_live = os.environ.get('FORCE_LIVE_MODE', '').lower() == 'true'
    
    if not market_status['is_open'] and not force_live:
        # Market is closed - auto-enable simulation, auto-trade, paper mode
        logger.info("🎮 Market closed - Auto-enabling: Simulation ON, Auto-Trade ON, Paper Mode ON")
        config.SIMULATION_MODE = True
        config.PAPER_TRADING_MODE = True
        db.save_state("simulation_mode", True)
        db.save_state("paper_trading_mode", True)
        db.save_state("auto_trading_enabled", True)  # Auto-enable trading in simulation
    elif force_live:
        # Force live mode - respect environment variables, don't auto-enable simulation
        logger.info("⚡ FORCE_LIVE_MODE enabled - Using environment settings (no auto-simulation)")
        logger.info(f"   Simulation: {config.SIMULATION_MODE}, Paper: {config.PAPER_TRADING_MODE}")
    else:
        # Market is open - use saved settings or defaults
        logger.info("🟢 Market is open - Using saved settings (configure manually if needed)")
        # Load from database if available
        saved_sim = db.get_state("simulation_mode")
        saved_paper = db.get_state("paper_trading_mode")
        if saved_sim is not None:
            config.SIMULATION_MODE = (saved_sim == "True")
        if saved_paper is not None:
            config.PAPER_TRADING_MODE = (saved_paper == "True")
    
    logger.info(f"⚙️  Current Config: Simulation={config.SIMULATION_MODE}, Paper={config.PAPER_TRADING_MODE}")
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
        webbrowser.open(f"http://localhost:{web_port}")
        logger.info(f"🚀 Opened browser at http://localhost:{web_port}")
    except Exception as e:
        logger.warning(f"Could not open browser: {e}")

    # Register explicit signal handlers
    import signal
    def handle_exit(signum, frame):
        logger.info(f"\nReceived signal {signum}. Shutting down...")
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Import and run web server
    from api.main import app
    
    logger.info(f"Starting FastAPI web server on port {web_port}...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=web_port,
        log_level="info"
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        sys.exit(0)
