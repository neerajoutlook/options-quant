import logging
import asyncio
from typing import Optional
from core.shoonya_client import ShoonyaSession
from .position_manager import PositionManager

logger = logging.getLogger(__name__)

class OrderManager:
    """
    Handles Order Placement and connects to PositionManager
    """
    def __init__(self, api_client: ShoonyaSession, position_mgr: PositionManager):
        self.api = api_client
        self.position_mgr = position_mgr
        
    def place_order(self, symbol: str, side: str, qty: int, tag: str = "MANUAL"):
        """Place order and update position (assuming fill for now - TODO: listen to socket)"""
        try:
            # 1. Place API Order
            logger.info(f"OMS Placing Order: {side} {qty} {symbol}")
            order_id = self.api.place_order(symbol, side, qty, "MARKET")
            
            # 2. Simulate Fill (Wait for socket in future phase)
            # For Manual UI feedback, we assume instant fill or wait for socket update.
            # Here we just log it so far. PositionManager update should ideally happen on `on_order_update` callback.
            # But for "Simulated" correctness in this phase:
            # self.position_mgr.on_fill(symbol, qty, <fetch_ltp>, side) 
            # We need LTP here.
            
            return order_id
        except Exception as e:
            logger.error(f"OMS Order Failed: {e}")
            return None

    async def close_all_positions(self):
        """Panic Exit / Risk Exit"""
        logger.warning("OMS: CLOSING ALL POSITIONS")
        for symbol, pos in self.position_mgr.positions.items():
            if pos["net_qty"] != 0:
                side = "SELL" if pos["net_qty"] > 0 else "BUY"
                qty = abs(pos["net_qty"])
                self.place_order(symbol, side, qty, "PANIC_EXIT")
                
