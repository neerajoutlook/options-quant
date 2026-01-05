import unittest
import time
from datetime import datetime
import pytz
from core.simulator import MarketSimulator

class TestMarketSimulator(unittest.TestCase):
    def setUp(self):
        self.ticks = []
        self.token_map = {
            "BANKNIFTY": "26009",
            "BN_48000_CE": "448000CE",
            "BN_48000_PE": "448000PE"
        }
        self.option_metadata = {
            "448000CE": {"type": "CE", "strike": 48000, "underlying": "BANKNIFTY"},
            "448000PE": {"type": "PE", "strike": 48000, "underlying": "BANKNIFTY"}
        }
        
    def on_tick(self, tick):
        self.ticks.append(tick)
        
    def test_simulator_pricing(self):
        sim = MarketSimulator(
            self.token_map, 
            self.on_tick, 
            option_metadata=self.option_metadata,
            speed=100.0 # Fast
        )
        
        # Override initial prices to be deterministic for test start
        sim.prices["26009"] = 48000.0 # Spot = Strike
        sim.prices["448000CE"] = 0.0
        sim.prices["448000PE"] = 0.0
        
        # Run one generation step
        # Using Random Walk for basic math test
        sim._process_random_walk_step()
        
        # Check Ticks
        self.assertTrue(len(self.ticks) >= 3)
        
        # Find ticks
        spot_tick = next(t for t in self.ticks if t['tk'] == '26009')
        ce_tick = next(t for t in self.ticks if t['tk'] == '448000CE')
        pe_tick = next(t for t in self.ticks if t['tk'] == '448000PE')
        
        # Check Timezone
        ist = pytz.timezone('Asia/Kolkata')
        ft_dt = datetime.fromtimestamp(spot_tick['ft'], ist)
        # Check offset (approximate check)
        self.assertEqual(ft_dt.tzinfo.zone, 'Asia/Kolkata')
        
        # Check Prices
        spot_price = float(spot_tick['lp'])
        ce_price = float(ce_tick['lp'])
        pe_price = float(pe_tick['lp'])
        
        print(f"Spot: {spot_price}, CE: {ce_price}, PE: {pe_price}")
        
        # Logic Check
        # If Spot > 48000, CE should have intrinsic value
        if spot_price > 48000:
            self.assertTrue(ce_price > (spot_price - 48000))
        
        # Ensure prices are not zero (should have time value)
        self.assertTrue(ce_price > 0)
        self.assertTrue(pe_price > 0)
        
if __name__ == '__main__':
    unittest.main()
