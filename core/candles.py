import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool = False

class CandleResampler:
    def __init__(self, interval_minutes: int):
        self.interval = interval_minutes
        self.current_candle: Optional[Candle] = None
        self.candles: List[Candle] = []
        
    def process_tick(self, price: float, volume: int, timestamp: datetime) -> Optional[Candle]:
        """
        Process a new tick and return a completed candle if a new bar starts.
        Returns None if the candle is still forming.
        """
        # Calculate the bucket start time for this tick
        # Example: 10:04:15 with 5min interval -> 10:00:00
        minute_floor = (timestamp.minute // self.interval) * self.interval
        bucket_start = timestamp.replace(minute=minute_floor, second=0, microsecond=0)
        
        completed_candle = None

        # If we have a current candle and this tick belongs to a NEW bucket
        if self.current_candle and bucket_start > self.current_candle.timestamp:
            # Finalize the previous candle
            self.current_candle.complete = True
            self.candles.append(self.current_candle)
            completed_candle = self.current_candle
            
            # Start a new candle
            self.current_candle = Candle(
                timestamp=bucket_start,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume
            )
            
        # If no current candle, start one
        elif self.current_candle is None:
            self.current_candle = Candle(
                timestamp=bucket_start,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume
            )
            
        # Update current candle
        else:
            self.current_candle.high = max(self.current_candle.high, price)
            self.current_candle.low = min(self.current_candle.low, price)
            self.current_candle.close = price
            self.current_candle.volume += volume # This assumes volume is cumulative or tick volume. 
                                                 # If tick volume is cumulative for the day, we need diff.
                                                 # For now assuming tick volume is "volume traded in this tick" 
                                                 # or we handle cumulative logic in the feed handler.

        return completed_candle

    def get_latest_candle(self) -> Optional[Candle]:
        return self.current_candle

    def get_history(self) -> pd.DataFrame:
        if not self.candles:
            return pd.DataFrame()
        
        data = [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in self.candles
        ]
        return pd.DataFrame(data).set_index("timestamp")
