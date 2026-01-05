"""
Market Data Aggregator - Central hub for real-time price data
Aggregates data from Shoonya feed and broadcasts to web clients
"""
import asyncio
from typing import Dict, Set, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MarketDataAggregator:
    """Aggregates and broadcasts market data to multiple subscribers"""
    
    def __init__(self):
        self.latest_prices: Dict[str, dict] = {}  # symbol -> price data
        self.subscribers: Set[Callable] = set()  # WebSocket broadcast callbacks
        self.lock = asyncio.Lock()
        
    async def update_price(self, symbol: str, tick_data: dict):
        """Update price data for a symbol"""
        async with self.lock:
            # Store latest tick
            self.latest_prices[symbol] = {
                'symbol': symbol,
                'ltp': float(tick_data.get('lp', 0)),
                'volume': int(tick_data.get('v', 0)),
                'open': float(tick_data.get('o', 0)),
                'high': float(tick_data.get('h', 0)),
                'low': float(tick_data.get('l', 0)),
                'change': float(tick_data.get('c', 0)),
                'timestamp': datetime.now().isoformat()
            }
            
        # Broadcast to all subscribers
        await self.broadcast(symbol, self.latest_prices[symbol])
    
    async def broadcast(self, symbol: str, data: dict):
        """Broadcast price update to all WebSocket clients"""
        if not self.subscribers:
            return
            
        # Create broadcast tasks
        tasks = []
        for callback in self.subscribers:
            tasks.append(callback(symbol, data))
        
        # Execute all broadcasts concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def subscribe(self, callback: Callable):
        """Subscribe to price updates"""
        self.subscribers.add(callback)
        logger.info(f"New subscriber added. Total: {len(self.subscribers)}")
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from price updates"""
        self.subscribers.discard(callback)
        logger.info(f"Subscriber removed. Total: {len(self.subscribers)}")
    
    def get_latest_prices(self) -> Dict[str, dict]:
        """Get all latest prices (for initial load)"""
        return self.latest_prices.copy()
    
    def get_price(self, symbol: str) -> dict:
        """Get latest price for specific symbol"""
        return self.latest_prices.get(symbol, {})

# Global instance
market_data = MarketDataAggregator()
