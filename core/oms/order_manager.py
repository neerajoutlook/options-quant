import logging
import asyncio
from typing import Optional
from core.shoonya_client import ShoonyaSession
from .position_manager import PositionManager
from core import config

logger = logging.getLogger(__name__)

class OrderManager:
    """
    Handles Order Placement and connects to PositionManager
    """
    def __init__(self, api_client: ShoonyaSession, position_mgr: PositionManager):
        self.api = api_client
        self.position_mgr = position_mgr
        self.paper_engine = None
        
        # Lazy load Paper Engine to avoid circular imports or early init issues
        if config.PAPER_TRADING_MODE or config.SIMULATION_MODE:
             from core.paper_trading import PaperTradingEngine
             self.paper_engine = PaperTradingEngine()

    def place_order(self, symbol: str, side: str, qty: int, product_type: str = 'I', tag: str = "MANUAL", price: float = 0.0):
        """
        Place order and update position.
        product_type: 'I' for MIS (Intraday derivatives), 'M' for NRML (Overnight), 'C' for CNC (Equity Delivery)
        price: Optional limit price or execution price for simulation. If 0 and MKT, uses best effort.
        """
        try:
            logger.info(f"OMS Placing Order: {side} {qty} {symbol} ({product_type}) Price: {price}")
            
            # --- SIMULATION / PAPER TRADING BYPASS ---
            if config.PAPER_TRADING_MODE or config.SIMULATION_MODE:
                import time
                import random
                
                sim_order_id = f"SIM_{int(time.time()*1000)}_{random.randint(100,999)}"
                
                # Determine Fill Price
                fill_price = price
                if fill_price <= 0:
                    # Try to fetch from PositionManager's internal tracking or use a placeholder
                    # PositionManager tracks avg_price, but not current LTP usually.
                    # Best attempt: 
                    # If we don't have a price, we log a warning.
                    # In Manual orders via API, price might be 0.
                    # Ideally the UI passes the last seen price?
                    fill_price = 1.0 # Fallback to avoid division by zero errors
                    logger.warning(f"OMS Simulation: No price provided for {symbol}. Using fallback {fill_price}")
                
                logger.info(f"📝 SIMULATION/PAPER: Simulating Fill for {symbol} Order {sim_order_id} @ {fill_price}")
                
                if self.paper_engine:
                    # Log to paper engine
                    self.paper_engine.enter_position(
                        signal_type=f"{side}_{product_type}",
                        entry_price=fill_price,
                        strike=0, 
                        quantity=qty,
                        reason=tag
                    )
                
                # Simulate Immediate Fill
                self.position_mgr.on_fill(symbol, qty, fill_price, side, product_type)
                
                return sim_order_id
            
            # --- REAL TRADING ---
            
            # Signature: buy_or_sell, product_type, exchange, tradingsymbol, quantity, discloseqty, price_type, ...
            buy_or_sell = side[0].upper() # 'B' or 'S'
            
            # Determine exchange and symbol suffix
            exchange = "NSE"
            # NFO check: has digits (options/futures) or is a known index name
            if any(char.isdigit() for char in symbol) or "CE" in symbol or "PE" in symbol or symbol in ["BANKNIFTY", "NIFTY", "FINNIFTY"]:
                exchange = "NFO"
            
            # Suffix logic for NSE Stocks
            elif exchange == "NSE" and not symbol.endswith("-EQ"):
                # Most Shoonya cash symbols need -EQ suffix
                symbol = f"{symbol}-EQ"
            
            logger.info(f"DEBUG OMS: Calling api.place_order with: buy_or_sell={buy_or_sell}, product_type={product_type}, exchange={exchange}, tradingsymbol={symbol}, quantity={qty}")
            
            order_id = self.api.place_order(
                buy_or_sell=buy_or_sell,
                product_type=product_type,
                exchange=exchange,
                tradingsymbol=symbol,
                quantity=qty,
                discloseqty=0,
                price_type="MKT",
                price=0.0
            )
            
            return order_id
        except Exception as e:
            logger.error(f"❌ OMS Order Failed: {e} for {symbol}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        return self.api.cancel_order(order_id)

    def place_gtt_order(self, symbol: str, side: str, qty: int, trigger_price: float, product_type: str = 'I'):
        """Place a GTT order"""
        # Determine exchange
        exchange = "NSE"
        if any(char.isdigit() for char in symbol) or "CE" in symbol or "PE" in symbol:
            exchange = "NFO"
            
        # Standard GTT behavior: Trigger Above for Buy (Resistance), Below for Sell (Stop Loss/Support)
        # BUT for Options, LTP Above is usually what we want for entry orders.
        alert_type = "LTP_ABOVE"
        
        return self.api.place_gtt_order(
            tradingsymbol=symbol,
            exchange=exchange,
            alert_type=alert_type,
            trigger_price=trigger_price,
            buy_or_sell=side[0].upper(),
            product_type=product_type,
            quantity=qty,
            price_type="MKT",
            price=0.0,
            remarks=f"GTT-{side}"
        )

    async def close_all_positions(self):
        """Panic Exit / Risk Exit for all products"""
        logger.warning("OMS: CLOSING ALL POSITIONS")
        for (symbol, product), pos in self.position_mgr.positions.items():
            if pos["net_qty"] != 0:
                side = "SELL" if pos["net_qty"] > 0 else "BUY"
                qty = abs(pos["net_qty"])
                logger.warning(f"OMS: Exiting {symbol} ({product}) Qty: {qty}")
                self.place_order(symbol, side, qty, product_type=product, tag="PANIC_EXIT")
                
