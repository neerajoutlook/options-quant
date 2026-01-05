#!/usr/bin/env python3
"""
Launch script for HFT Web Platform - DEMO MODE
Runs web server with simulated price data (no Shoonya connection needed)
"""
import sys
import asyncio
import uvicorn
import random
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from api.main import app
from core.market_data import market_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Demo symbols
DEMO_SYMBOLS = {
    'BANKNIFTY': {'base': 59500, 'volatility': 100},
    'HDFCBANK': {'base': 1650, 'volatility': 5},
    'ICICIBANK': {'base': 985, 'volatility': 3},
    'SBIN': {'base': 625, 'volatility': 2},
    'KOTAKBANK': {'base': 1750, 'volatility': 6},
    'AXISBANK': {'base': 1055, 'volatility': 4},
    'INDUSINDBK': {'base': 1420, 'volatility': 5},
    'BANDHANBNK': {'base': 195, 'volatility': 1.5},
    'FEDERALBNK': {'base': 155, 'volatility': 1},
    'IDFCFIRSTB': {'base': 68, 'volatility': 0.5},
    'PNB': {'base': 95, 'volatility': 0.8},
    'AUBANK': {'base': 585, 'volatility': 2.5},
}

class MockPriceSimulator:
    """Generates realistic-looking mock price data"""
    
    def __init__(self):
        self.prices = {}
        self.opens = {}
        self.highs = {}
        self.lows = {}
        self.volumes = {}
        
        # Initialize prices
        for symbol, config in DEMO_SYMBOLS.items():
            self.prices[symbol] = config['base']
            self.opens[symbol] = config['base']
            self.highs[symbol] = config['base']
            self.lows[symbol] = config['base']
            self.volumes[symbol] = random.randint(100000, 500000)
    
    async def simulate_price_updates(self):
        """Continuously generate price updates"""
        logger.info("Starting mock price simulation...")
        
        while True:
            # Update each symbol
            for symbol, config in DEMO_SYMBOLS.items():
                # Random walk with mean reversion
                change = random.gauss(0, config['volatility'])
                new_price = self.prices[symbol] + change
                
                # Mean reversion towards base
                if abs(new_price - config['base']) > config['volatility'] * 3:
                    reversion = (config['base'] - new_price) * 0.1
                    new_price += reversion
                
                self.prices[symbol] = new_price
                self.highs[symbol] = max(self.highs[symbol], new_price)
                self.lows[symbol] = min(self.lows[symbol], new_price)
                self.volumes[symbol] += random.randint(100, 1000)
                
                # Create tick data
                tick_data = {
                    'lp': new_price,  # Last price
                    'o': self.opens[symbol],  # Open
                    'h': self.highs[symbol],  # High
                    'l': self.lows[symbol],  # Low
                    'v': self.volumes[symbol],  # Volume
                    'c': new_price - self.opens[symbol],  # Change
                }
                
                # Broadcast to web clients
                await market_data.update_price(symbol, tick_data)
            
            # Update every 100-500ms for realistic feel
            await asyncio.sleep(random.uniform(0.1, 0.5))

async def run_simulator():
    """Run the price simulator"""
    simulator = MockPriceSimulator()
    await simulator.simulate_price_updates()

def run_web_server():
    """Run FastAPI server with simulator in background"""
    logger.info("=" * 60)
    logger.info("HFT Web Trading Platform - DEMO MODE")
    logger.info("=" * 60)
    logger.info("📊 Dashboard: http://localhost:8000")
    logger.info("🔄 Simulated price updates: ~5-10 updates/sec")
    logger.info("=" * 60)
    
    # Start price simulator in background
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_simulator())
    
    # Run web server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        loop="asyncio"
    )
    server = uvicorn.Server(config)
    server.run()

if __name__ == "__main__":
    try:
        run_web_server()
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        sys.exit(0)
