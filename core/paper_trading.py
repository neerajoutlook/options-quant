"""
Paper Trading Module - Track simulated trades without real broker integration
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class PaperTrade:
    """Represents a simulated trade"""
    entry_time: str
    entry_price: float
    entry_strike: int
    option_type: str  # 'CE' or 'PE'
    quantity: int
    entry_reason: str
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    status: str = "OPEN"  # OPEN, CLOSED
    
class PaperTradingEngine:
    """Simulates order execution and tracks P&L"""
    
    def __init__(self):
        self.current_position: Optional[PaperTrade] = None
        self.closed_trades: List[PaperTrade] = []
        self.trades_file = Path("logs/paper_trades.json")
        self.trades_file.parent.mkdir(exist_ok=True)
        
    def enter_position(self, signal_type: str, entry_price: float, strike: int, 
                       quantity: int, reason: str) -> PaperTrade:
        """
        Simulate entering a position
        Assumes market order fills at signal price (simplified)
        """
        option_type = "CE" if "CE" in signal_type else "PE"
        
        self.current_position = PaperTrade(
            entry_time=datetime.now().isoformat(),
            entry_price=entry_price,
            entry_strike=strike,
            option_type=option_type,
            quantity=quantity,
            entry_reason=reason
        )
        
        logger.info(f"📝 Paper Trade ENTRY: {option_type} {strike} @ ₹{entry_price:.2f}")
        return self.current_position
    
    def exit_position(self, exit_price: float, reason: str) -> Optional[float]:
        """
        Simulate exiting the position
        Calculate P&L (simplified - uses spot price movement as proxy)
        """
        if not self.current_position:
            return None
        
        # Simple P&L calculation based on spot movement
        # Real P&L would need actual option premium tracking
        price_diff = exit_price - self.current_position.entry_price
        
        # For options: if CE and price went up, profit. If PE and price went down, profit
        if self.current_position.option_type == "CE":
            pnl = price_diff * self.current_position.quantity
        else:  # PE
            pnl = -price_diff * self.current_position.quantity
        
        self.current_position.exit_time = datetime.now().isoformat()
        self.current_position.exit_price = exit_price
        self.current_position.pnl = pnl
        self.current_position.status = "CLOSED"
        
        self.closed_trades.append(self.current_position)
        self._save_trade(self.current_position)
        
        logger.info(f"📝 Paper Trade EXIT: @ ₹{exit_price:.2f} | P&L: ₹{pnl:.2f}")
        
        self.current_position = None
        return pnl
    
    def _save_trade(self, trade: PaperTrade):
        """Save trade to JSON file"""
        trades = []
        if self.trades_file.exists():
            with open(self.trades_file, 'r') as f:
                try:
                    trades = json.load(f)
                except:
                    trades = []
        
        trades.append(asdict(trade))
        
        with open(self.trades_file, 'w') as f:
            json.dump(trades, f, indent=2)
    
    def get_daily_pnl(self) -> Dict:
        """Calculate today's paper trading P&L"""
        today = datetime.now().date().isoformat()
        
        if not self.trades_file.exists():
            return {
                "date": today,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "gross_pnl": 0,
                "win_rate": 0,
                "trades": []
            }
        
        with open(self.trades_file, 'r') as f:
            try:
                all_trades = json.load(f)
            except:
                all_trades = []
        
        # Filter today's closed trades
        today_trades = [
            t for t in all_trades 
            if t.get('exit_time') and t['exit_time'].startswith(today)
        ]
        
        total_trades = len(today_trades)
        winning_trades = len([t for t in today_trades if t.get('pnl', 0) > 0])
        losing_trades = len([t for t in today_trades if t.get('pnl', 0) < 0])
        gross_pnl = sum([t.get('pnl', 0) for t in today_trades])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "date": today,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "gross_pnl": gross_pnl,
            "win_rate": win_rate,
            "trades": today_trades
        }
