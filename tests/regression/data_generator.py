import math
import time
from typing import List, Dict

class DataGenerator:
    """
    Generates deterministic market data for regression testing.
    Uses sine waves to create predictable trend reversals.
    """
    def __init__(self, token_map: Dict[str, str]):
        self.token_map = token_map
        self.start_price = 48000.0
        self.start_time = 1700000000 # Deterministic start timestamp
        
    def generate_sine_wave(self, symbol: str, duration_minutes: int = 10, period_minutes: int = 5) -> List[Dict]:
        """
        Generate ticks following a sine wave pattern.
        
        Args:
            symbol: Stock symbol (e.g., BANKNIFTY)
            duration_minutes: Total duration of data to generate
            period_minutes: Time for one full cycle (Low -> High -> Low)
        
        Returns:
            List of tick dictionaries compatible with TickEngine
        """
        ticks = []
        token = self.token_map.get(symbol, "26009")
        
        # 1 tick per second
        total_steps = duration_minutes * 60
        amplitude = 100.0 # Points swing
        
        for i in range(total_steps):
            t = i
            
            # Sine Wave Calculation
            # period = 2*pi
            # cycle = period_minutes * 60 seconds
            angle = (2 * math.pi * t) / (period_minutes * 60)
            
            # Price oscillation
            price_change = amplitude * math.sin(angle)
            current_price = self.start_price + price_change
            
            # Volume (randomized but deterministic seed if needed, here just constant)
            volume = 100 + (i % 50)
            
            # Timestamp
            ts = self.start_time + i
            
            tick = {
                'tk': token,
                'lp': f"{current_price:.2f}", # Shoonya sends prices as strings often
                'ft': str(ts),
                'v': str(volume), # Volume as string
                'pc': '0.0', # Percent change (calculated on fly usually)
                'o': str(self.start_price),
                'h': str(max(self.start_price, current_price)),
                'l': str(min(self.start_price, current_price)),
                'c': str(self.start_price)
            }
            ticks.append(tick)
            
        return ticks

if __name__ == "__main__":
    # Test
    gen = DataGenerator({"BANKNIFTY": "26009"})
    data = gen.generate_sine_wave("BANKNIFTY", duration_minutes=1)
    print(f"Generated {len(data)} ticks")
    print(f"First: {data[0]['lp']}")
    print(f"Peak (approx): {data[150]['lp']}") # 2.5 min peak in 5 min cycle? 5 min period -> peak at 1.25m = 75s
