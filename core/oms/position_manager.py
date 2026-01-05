import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PositionManager:
    """
    Tracks positions, average price, and P&L.
    Enforces risk limits.
    """
    def __init__(self, risk_config: Dict = None):
        self.positions = {} # Symbol -> { net_qty, avg_price, realized_pnl, unrealized_pnl }
        self.risk_config = risk_config or {"max_drawdown_pct": 2.0, "capital": 100000}
        self.realized_pnl = 0.0
        
    def on_fill(self, symbol: str, quantity: int, price: float, side: str):
        """Update position on order fill"""
        if symbol not in self.positions:
            self.positions[symbol] = {"net_qty": 0, "avg_price": 0.0, "realized_pnl": 0.0, "unrealized_pnl": 0.0}
            
        pos = self.positions[symbol]
        fill_qty = quantity if side == 'BUY' else -quantity
        
        # P&L Logic (Simplified FIFO/Avg Price for now)
        # If closing (reducing size), calculate Realized P&L
        # If opening (increasing size), update Avg Price
        
        # Current Logic: Simple Average Price implementation
        if pos["net_qty"] == 0:
            pos["avg_price"] = price
            pos["net_qty"] = fill_qty
        elif (pos["net_qty"] > 0 and fill_qty > 0) or (pos["net_qty"] < 0 and fill_qty < 0):
            # Adding to position
            total_val = (pos["net_qty"] * pos["avg_price"]) + (fill_qty * price)
            pos["net_qty"] += fill_qty
            pos["avg_price"] = total_val / pos["net_qty"]
        else:
            # Closing position (partial or full)
            closing_qty = abs(fill_qty)
            opening_qty = abs(pos["net_qty"])
            
            # P&L on the closed portion
            profit = (price - pos["avg_price"]) * closing_qty if pos["net_qty"] > 0 else (pos["avg_price"] - price) * closing_qty
            pos["realized_pnl"] += profit
            self.realized_pnl += profit
            
            pos["net_qty"] += fill_qty
            if pos["net_qty"] == 0:
                pos["avg_price"] = 0.0
                
        logger.info(f"Position Updated: {symbol} Qty: {pos['net_qty']} Avg: {pos['avg_price']:.2f} P&L: {pos['realized_pnl']:.2f}")

    def update_pnl(self, market_prices: Dict[str, float]):
        """Calculate Unrealized P&L based on live prices"""
        total_unrealized = 0.0
        
        for symbol, pos in self.positions.items():
            if pos["net_qty"] == 0:
                pos["unrealized_pnl"] = 0.0
                continue
                
            ltp = market_prices.get(symbol, pos["avg_price"])
            if pos["net_qty"] > 0:
                pos["unrealized_pnl"] = (ltp - pos["avg_price"]) * pos["net_qty"]
            else:
                pos["unrealized_pnl"] = (pos["avg_price"] - ltp) * abs(pos["net_qty"])
                
            total_unrealized += pos["unrealized_pnl"]
            
        return total_unrealized

    def check_risk(self, total_unrealized: float) -> bool:
        """Return True if risk limit breached (Stop Loss)"""
        total_pnl = self.realized_pnl + total_unrealized
        limit = -1 * (self.risk_config["capital"] * (self.risk_config["max_drawdown_pct"] / 100))
        
        if total_pnl < limit:
            logger.warning(f"RISK BREACH: P&L {total_pnl} < Limit {limit}. Triggering Exit.")
            return True
        return False
