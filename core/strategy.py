import pandas as pd
import logging
from core import config
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
        
    def set_open_price(self, symbol: str, price: float):
        """Manually set the open price (e.g., from history)"""
        if symbol in self.weights:
            self.open_prices[symbol] = price
            logger.info(f"📊 Weightage: Set OPEN for {symbol} to {price:.2f}")

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
    def __init__(self, weightage_calc: WeightageCalculator, min_strength: float = 2.5, min_hold_time: int = 60, min_confirmation: int = 5):
        """
        Args:
            weightage_calc: WeightageCalculator instance
            min_strength: Minimum score threshold for entry
            min_hold_time: Minimum seconds between signals
            min_confirmation: Number of ticks for validation
        """
        self.weightage_calc = weightage_calc
        self.position = None # None, "CE", "PE"
        self.threshold = min_strength
        self.min_hold_time = min_hold_time
        self.confirmation_count = min_confirmation
        self.last_signal_time = 0  
        
        # New: Tracking for higher reliability
        self.score_buffer = [] # List of recent total scores
        self.price_history = [] # List of (timestamp, price) for momentum

    def _calculate_momentum(self, current_price: float, current_time: float) -> float:
        """Calculate momentum score based on change over last 2-5 minutes"""
        self.price_history.append((current_time, current_price))
        
        # Cleanup: Keep 10 minutes of history
        while self.price_history and current_time - self.price_history[0][0] > 600:
            self.price_history.pop(0)
            
        if len(self.price_history) < 2:
            return 0.0
            
        # Look back ~2 minutes (120s)
        lookback_time = current_time - 120
        old_price = self.price_history[0][1]
        for t, p in reversed(self.price_history):
            if t <= lookback_time:
                old_price = p
                break
        
        change_points = current_price - old_price
        
        # Scoring Momentum: 
        # +30 points move (~0.05%) -> +0.5 score
        # +60 points move (~0.10%) -> +1.5 score (Strong bounce)
        mom_score = 0.0
        if change_points >= 60: mom_score = 1.5
        elif change_points >= 30: mom_score = 0.5
        elif change_points <= -60: mom_score = -1.5
        elif change_points <= -30: mom_score = -0.5
        
        return mom_score

    def on_tick(self, price: float, timestamp: float, vwap: float = 0, macro_trend: str = "NEUTRAL") -> Optional[Signal]:
        """
        Enhanced AI Scoring with Momentum and Validation
        """
        # 1. Constituent Strength
        strength = self.weightage_calc.calculate_weighted_strength()
        
        # 2. Momentum Score
        mom_score = self._calculate_momentum(price, timestamp)
        
        # 3. Base Score Calculation
        score = 0
        
        # Factor A: Intraday Trend (Relative to Prev Close/VWAP)
        if vwap > 0:
            if price > vwap: score += 1.0
            elif price < vwap: score -= 1.0
        
        # Factor B: Macro context
        if macro_trend == "BULLISH": score += 1.0
        elif macro_trend == "BEARISH": score -= 1.0
        
        # Factor C: Constituent Strength
        if strength > 20: score += 1.5
        elif strength > 10: score += 0.5
        elif strength < -20: score -= 1.5
        elif strength < -10: score -= 0.5
        
        # Factor D: Momentum (The "Turnaround" factor)
        score += mom_score

        # --- SIMULATION BOOST ---
        # Random walk data is too noisy/flat for strict strategy.
        # Boost score loosely to demonstrate auto-trading mechanics
        if config.SIMULATION_MODE and self.position is None:
             if score > 0.5: score += 1.5 # Boost weak buy
             elif score < -0.5: score -= 1.5 # Boost weak sell

        
        # 4. Signal Smoothing
        self.score_buffer.append(score)
        if len(self.score_buffer) > self.confirmation_count:
            self.score_buffer.pop(0)
            
        # Check if score is consistently high/low
        if len(self.score_buffer) < self.confirmation_count:
            return None
            
        avg_score = sum(self.score_buffer) / len(self.score_buffer)

        # 5. Signal Generation Logic
        time_since_last_signal = timestamp - self.last_signal_time
        if time_since_last_signal < self.min_hold_time and self.last_signal_time > 0:
            return None

        signal = None
        
        if self.position is None:
            # Conviction excluding momentum
            conviction = avg_score - mom_score
            
            # 1. High Conviction Directional (CE/PE)
            if avg_score >= self.threshold:
                reason = f"Score {avg_score:.1f} (Mom: {mom_score:+.1f})"
                signal = Signal("BUY_CE", "BANKNIFTY", price, reason, timestamp)
                self.position = "CE"
                self.last_signal_time = timestamp
            elif avg_score <= -self.threshold:
                reason = f"Score {avg_score:.1f} (Mom: {mom_score:+.1f})"
                signal = Signal("BUY_PE", "BANKNIFTY", price, reason, timestamp)
                self.position = "PE"
                self.last_signal_time = timestamp
            
            # 2. Low Conviction but High Momentum (Neutral Straddle)
            elif config.ENABLE_STRADDLES and abs(conviction) < 1.0 and abs(mom_score) >= 1.5:
                reason = f"Straddle: Conviction {conviction:.1f}, Mom Spike {mom_score:+.1f}"
                signal = Signal("BUY_STRADDLE", "BANKNIFTY", price, reason, timestamp)
                self.position = "STRADDLE"
                self.last_signal_time = timestamp
                
        elif self.position == "CE":
            # Exit on score drop or reversal
            if avg_score < 0.5:
                signal = Signal("EXIT", "BANKNIFTY", price, f"Score faded to {avg_score:.1f}", timestamp)
                self.position = None
                self.last_signal_time = timestamp
                
        elif self.position == "PE":
            # Exit on score rise or reversal
            if avg_score > -0.5:
                signal = Signal("EXIT", "BANKNIFTY", price, f"Score faded to {avg_score:.1f}", timestamp)
                self.position = None
                self.last_signal_time = timestamp

        elif self.position == "STRADDLE":
            # Exit on momentum fade or conviction shift
            if abs(mom_score) < 0.5 or abs(avg_score) > self.threshold:
                signal = Signal("EXIT", "BANKNIFTY", price, f"Straddle fade (Mom: {mom_score:.1f})", timestamp)
                self.position = None
                self.last_signal_time = timestamp
                
        return signal
