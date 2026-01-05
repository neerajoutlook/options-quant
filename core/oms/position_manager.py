import logging
from core import config

logger = logging.getLogger(__name__)
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
        
        # Persistence
        try:
            from core.database import db
            self.db = db
            self._load_state()
        except Exception as e:
            logger.error(f"Failed to initialize PositionManager DB: {e}")
            self.db = None

    def _load_state(self):
        """Load state from database"""
        if not self.db: return
        self.positions = self.db.get_positions()
        self.realized_pnl = float(self.db.get_state("realized_pnl", 0.0))
        logger.info(f"💾 PositionManager loaded state: {len(self.positions)} positions, Realized P&L: {self.realized_pnl:.2f}")

    def on_fill(self, symbol: str, quantity: int, price: float, side: str, product: str = 'I'):
        """Update position on order fill (keyed by symbol and product)"""
        pos_key = (symbol, product)
        if pos_key not in self.positions:
            self.positions[pos_key] = {"net_qty": 0, "avg_price": 0.0, "realized_pnl": 0.0, "unrealized_pnl": 0.0}
            
        pos = self.positions[pos_key]
        fill_qty = quantity if side == 'BUY' else -quantity
        
        # P&L Logic (Simplified Average Price implementation)
        if pos["net_qty"] == 0:
            pos["avg_price"] = price
            pos["net_qty"] = fill_qty
            pos["entry_time"] = datetime.now().strftime("%H:%M:%S")
        elif (pos["net_qty"] > 0 and fill_qty > 0) or (pos["net_qty"] < 0 and fill_qty < 0):
            # Adding to position
            total_val = (pos["net_qty"] * pos["avg_price"]) + (fill_qty * price)
            pos["net_qty"] += fill_qty
            pos["avg_price"] = total_val / pos["net_qty"]
        else:
            # Closing position (partial or full)
            closing_qty = abs(fill_qty)
            
            # P&L on the closed portion
            profit = (price - pos["avg_price"]) * closing_qty if pos["net_qty"] > 0 else (pos["avg_price"] - price) * closing_qty
            pos["realized_pnl"] += profit
            self.realized_pnl += profit
            
            pos["net_qty"] += fill_qty
            if pos["net_qty"] == 0:
                pos["avg_price"] = 0.0
                
        logger.info(f"Position Updated: {symbol} ({product}) Qty: {pos['net_qty']} Avg: {pos['avg_price']:.2f} P&L: {pos['realized_pnl']:.2f}")

        # Persistence
        if self.db:
            self.db.save_position(symbol, pos, product=product)
            self.db.save_state("realized_pnl", self.realized_pnl)

    def update_pnl(self, market_prices: Dict[str, float]):
        """Calculate Unrealized P&L based on live prices"""
        total_unrealized = 0.0
        
        for (symbol, product), pos in self.positions.items():
            if pos["net_qty"] == 0:
                pos["unrealized_pnl"] = 0.0
                continue
                
            # market_prices is Dict[str, dict] mapping symbol to data
            p_data = market_prices.get(symbol)
            ltp = p_data.get('ltp', pos["avg_price"]) if p_data else pos["avg_price"]
            if pos["net_qty"] > 0:
                pos["unrealized_pnl"] = (ltp - pos["avg_price"]) * pos["net_qty"]
            else:
                pos["unrealized_pnl"] = (pos["avg_price"] - ltp) * abs(pos["net_qty"])
                
            total_unrealized += pos["unrealized_pnl"]
            
            # Update Trailing SL if position exists
            if pos["net_qty"] != 0:
                self._manage_tsl(pos, ltp)
                
        return total_unrealized

    def _manage_tsl(self, pos: Dict, ltp: float):
        """
        Internal TSL logic: Activate at 5% profit, then trail by 5%.
        """
        if pos["net_qty"] == 0: return
        
        # Calculate current profit percentage
        # For Long: (LTP - Avg) / Avg * 100
        # For Short: (Avg - LTP) / Avg * 100
        side = 1 if pos["net_qty"] > 0 else -1
        profit_pct = side * (ltp - pos["avg_price"]) / pos["avg_price"] * 100
        
        # Hurdle and Trail from config
        hurdle = config.TSL_PROFIT_HURDLE
        trail = config.TSL_TRAIL_PERCENT
        
        if not pos.get("tsl_active"):
            if profit_pct >= hurdle:
                pos["tsl_active"] = True
                pos["hwm"] = ltp # High Water Mark
                # Initial trigger set at HWM - trail%
                pos["tsl_trigger"] = ltp * (1 - (trail/100) * side)
                logger.info(f"🚀 TSL ACTIVATED for position at {ltp:.2f} (Profit: {profit_pct:.2f}%)")
        else:
            # TSL is active, check for HWM update or pull back breach
            # For Long: HWM is max price, exit if LTP falls below HWM - 5%
            # For Short: HWM is min price, exit if LTP rises above HWM + 5%
            if side == 1: # LONG
                if ltp > pos["hwm"]:
                    pos["hwm"] = ltp
                    pos["tsl_trigger"] = ltp * (1 - trail/100)
                elif ltp < pos["tsl_trigger"]:
                    pos["tsl_breached"] = True
                    logger.warning(f"⚠️ TSL BREACHED (Long) at {ltp:.2f}. Trigger: {pos['tsl_trigger']:.2f}")
            else: # SHORT
                if ltp < pos["hwm"]:
                    pos["hwm"] = ltp
                    pos["tsl_trigger"] = ltp * (1 + trail/100)
                elif ltp > pos["tsl_trigger"]:
                    pos["tsl_breached"] = True
                    logger.warning(f"⚠️ TSL BREACHED (Short) at {ltp:.2f}. Trigger: {pos['tsl_trigger']:.2f}")

    def check_tsl_breach(self, symbol: str, product: str) -> bool:
        """Check if a position has breached its TSL"""
        pos = self.positions.get((symbol, product))
        if pos and pos.get("tsl_breached"):
            return True
        return False


    def check_risk(self, total_unrealized: float) -> bool:
        """Return True if risk limit breached (Stop Loss)"""
        total_pnl = self.realized_pnl + total_unrealized
        limit = -1 * (self.risk_config["capital"] * (self.risk_config["max_drawdown_pct"] / 100))
        
        if total_pnl < limit:
            logger.warning(f"RISK BREACH: P&L {total_pnl} < Limit {limit}. Triggering Exit.")
            return True
        return False
