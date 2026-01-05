import pandas as pd
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Bank Nifty Constituents with approximate weights (as of 2024)
# These are the major banking stocks that comprise Bank Nifty
BANKNIFTY_WEIGHTS = {
    "HDFCBANK": 28.0,      # HDFC Bank - highest weight
    "ICICIBANK": 24.0,     # ICICI Bank
    "SBIN": 10.0,          # State Bank of India
    "KOTAKBANK": 12.0,     # Kotak Mahindra Bank
    "AXISBANK": 11.0,      # Axis Bank
    "INDUSINDBK": 5.0,     # IndusInd Bank
    "BANDHANBNK": 2.5,     # Bandhan Bank
    "FEDERALBNK": 2.0,     # Federal Bank
    "IDFCFIRSTB": 1.5,     # IDFC First Bank
    "PNB": 2.0,            # Punjab National Bank
    "AUBANK": 2.0,         # AU Small Finance Bank
}

# Alternative: NIFTY 50 constituents (keeping for future use)
NIFTY_WEIGHTS = {
    "RELIANCE": 10.0,
    "TCS": 6.5,
    "HDFCBANK": 8.0,
    "INFY": 5.5,
    "ICICIBANK": 5.0,
    "HINDUNILVR": 3.5,
    "ITC": 3.0,
    "BHARTIARTL": 4.0,
    "SBIN": 3.0,
    "LT": 3.5,
    "KOTAKBANK": 3.0,
    "AXISBANK": 2.5,
    "BAJFINANCE": 3.5,
    "ASIANPAINT": 2.0,
    "MARUTI": 2.5,
}

@dataclass
class Signal:
    type: str  # "BUY_CE", "BUY_PE", "EXIT"
    symbol: str
    price: float
    reason: str
    timestamp: float

class WeightageCalculator:
    """Calculate real-time weighted strength based on constituent price changes."""
    
    def __init__(self, weights: Dict[str, float] = None, use_volume: bool = False):
        """
        Initialize with stock weights.
        Args:
            weights: Dictionary of {symbol: weight_percentage}. Defaults to BANKNIFTY_WEIGHTS.
            use_volume: Whether to use volume in strength calculation.
        """
        self.weights = weights or BANKNIFTY_WEIGHTS
        self.use_volume = use_volume
        self.open_prices: Dict[str, float] = {}
        self.current_prices: Dict[str, float] = {}
        self.current_volumes: Dict[str, float] = {}
        self.initial_volumes: Dict[str, float] = {} # Volume at start of day/session
        
    def update_data(self, symbol: str, price: float, volume: float = 0, is_open: bool = False):
        """Update price and volume for a symbol."""
        if symbol not in self.weights:
            return
            
        self.current_prices[symbol] = price
        self.current_volumes[symbol] = volume
        
        if is_open or symbol not in self.open_prices:
            self.open_prices[symbol] = price
            self.initial_volumes[symbol] = volume
    
    def calculate_weighted_strength(self) -> float:
        """
        Calculate the weighted strength of the index.
        Returns a value representing the weighted % change sum.
        Positive = Bullish, Negative = Bearish.
        """
        total_strength = 0.0
        
        for symbol in self.weights.keys():
            if symbol not in self.open_prices or symbol not in self.current_prices:
                continue
            if self.open_prices[symbol] == 0:
                continue
                
            pct_change = (self.current_prices[symbol] - self.open_prices[symbol]) / self.open_prices[symbol] * 100
            weight = self.weights.get(symbol, 0)
            
            contribution = pct_change * weight
            
            # Experimental: Volume Weighting
            # If enabled, boost contribution if volume is significant
            # (Simple implementation: Multiply by log of volume relative to others? 
            #  For now, just a placeholder for the logic as we lack historical avg volume)
            if self.use_volume and symbol in self.current_volumes:
                # This is a placeholder for volume logic
                # Real implementation needs Relative Volume (RVOL)
                pass
                
            total_strength += contribution
            
        return total_strength

class TechnicalIndicators:
    """Helper for technical analysis."""
    
    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macro_trend(history_df: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate macro trend from hourly data.
        Returns: {'trend': 'BULLISH'|'BEARISH', 'rsi': float, 'message': str}
        """
        if history_df.empty or len(history_df) < 50:
            return {'trend': 'NEUTRAL', 'rsi': 0, 'message': 'Insufficient Data'}
            
        # Ensure numeric
        close = pd.to_numeric(history_df['close'])
        
        # 1. 50-Period SMA
        sma_50 = close.rolling(window=50).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        # 2. RSI 14
        rsi_series = TechnicalIndicators.calculate_rsi(close, 14)
        rsi = rsi_series.iloc[-1]
        
        # Determine Trend
        trend = "NEUTRAL"
        if current_price > sma_50:
            trend = "BULLISH"
        elif current_price < sma_50:
            trend = "BEARISH"
            
        # RSI Filter
        message = f"RSI: {rsi:.1f}"
        if rsi > 70: message += " (Overbought)"
        if rsi < 30: message += " (Oversold)"
        
        return {
            'trend': trend,
            'rsi': round(rsi, 2),
            'sma': round(sma_50, 2),
            'message': message
        }

class Strategy:
    def __init__(self, weightage_calc: WeightageCalculator, min_strength: float = 5.5, min_hold_time: int = 60):
        """
        Args:
            weightage_calc: WeightageCalculator instance
            min_strength: Minimum strength threshold for signals (higher = high conviction)
            min_hold_time: Minimum seconds between signals (prevents churn)
        """
        self.weightage_calc = weightage_calc
        self.position = None # None, "CE", "PE"
        self.threshold = min_strength
        self.min_hold_time = min_hold_time
        self.last_signal_time = 0  # Track last signal timestamp

    def on_tick(self, sensex_price: float, timestamp: float) -> Optional[Signal]:
        strength = self.weightage_calc.calculate_weighted_strength()
        
        # Check if enough time passed since last signal
        time_since_last_signal = timestamp - self.last_signal_time
        if time_since_last_signal < self.min_hold_time and self.last_signal_time > 0:
            return None  # Too soon, prevent churn
        
        # Simple Logic:
        # If Strength > Threshold -> BUY CE
        # If Strength < -Threshold -> BUY PE
        #If Strength drops near 0 -> EXIT
        
        signal = None
        
        if self.position is None:
            if strength > self.threshold:
                signal = Signal("BUY_CE", "BANKNIFTY", sensex_price, f"Strength {strength:.2f} > {self.threshold}", timestamp)
                self.position = "CE"
                self.last_signal_time = timestamp
            elif strength < -self.threshold:
                signal = Signal("BUY_PE", "BANKNIFTY", sensex_price, f"Strength {strength:.2f} < -{self.threshold}", timestamp)
                self.position = "PE"
                self.last_signal_time = timestamp
                
        elif self.position == "CE":
            if strength < 1.0: # Exit if strength fades
                signal = Signal("EXIT", "BANKNIFTY", sensex_price, f"Strength faded to {strength:.2f}", timestamp)
                self.position = None
                self.last_signal_time = timestamp
                
        elif self.position == "PE":
            if strength > -1.0: # Exit if weakness fades
                signal = Signal("EXIT", "BANKNIFTY", sensex_price, f"Strength faded to {strength:.2f}", timestamp)
                self.position = None
                self.last_signal_time = timestamp
                
        return signal
