import unittest
from unittest.mock import MagicMock
import time
from core.simulator import MarketSimulator

class TestMarketSimulator(unittest.TestCase):
    def setUp(self):
        self.token_map = {
            'BANKNIFTY': '26009',
            'HDFCBANK': '1333'
        }
        self.ticks = []
        
        def on_tick(tick):
            self.ticks.append(tick)
            
        self.simulator = MarketSimulator(self.token_map, on_tick, speed=10.0) # High speed for test
        
    def tearDown(self):
        self.simulator.stop()
        
    def test_initialization(self):
        """Verify simulator initializes prices for tracked tokens."""
        self.assertEqual(len(self.simulator.prices), 2)
        self.assertIn('26009', self.simulator.prices)
        self.assertGreater(self.simulator.prices['26009'], 0)
        
    def test_tick_generation(self):
        """Verify ticks are generated and callback is invoked."""
        self.simulator.start()
        time.sleep(1) 
        self.simulator.stop()
        
        self.assertGreater(len(self.ticks), 0)
        
        first_tick = self.ticks[0]
        self.assertIn('tk', first_tick)
        self.assertIn('lp', first_tick)
        self.assertIn('v', first_tick)
        
        # Verify tokens match
        tokens = set(t['tk'] for t in self.ticks)
        self.assertIn('26009', tokens)
        self.assertIn('1333', tokens)
        
    def test_price_movement(self):
        """Verify prices change over time (Random Walk)."""
        self.simulator.start()
        time.sleep(1)
        self.simulator.stop()
        
        bn_ticks = [t for t in self.ticks if t['tk'] == '26009']
        prices = [float(t['lp']) for t in bn_ticks]
        
        # Prices should not be all identical (extremely unlikely)
        unique_prices = set(prices)
        self.assertGreater(len(unique_prices), 1)

if __name__ == '__main__':
    unittest.main()
