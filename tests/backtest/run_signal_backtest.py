
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
from collections import defaultdict

# Add project root
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.strategy import Strategy
# from core.utils import get_india_time
# Strategy expects datetime objects.

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Backtest")

class MockWeightage:
    """Strategy needs a calculator, we mock it since we are Spot-only backtesting."""
    def get_market_sentiment(self):
        return 0 # Neutral, or we can simulate this?
    
    def calculate_weighted_strength(self):
        return 0.0 # Neutral strength

class SignalBacktester:
    def __init__(self, data_path):
        self.data_path = data_path
        # Reduce confirmation to 1 to capture all raw signals for analysis
        self.strategy = Strategy(weightage_calc=MockWeightage(), min_confirmation=1)
        self.signals = []
        self.candles = []
        
    def load_data(self):
        logger.info(f"Loading data from {self.data_path}...")
        with open(self.data_path, 'r') as f:
            raw = json.load(f)
            
        # Convert to DataFrame-like structure for easy lookup
        # Shoonya JSON: {'time': '05-01-2026 15:29:00', 'intc': '60055.50', ...}
        # Strategy Logic relies on: strategy.on_tick(tick=None, price=..., timestamp=...)
        # We need to parse timestamps carefully.
        
        self.candles = []
        for r in raw:
            try:
                # Format: 05-01-2026 15:29:00
                dt = datetime.strptime(r['time'], "%d-%m-%Y %H:%M:%S")
                price = float(r['intc'])
                self.candles.append({
                    'ts': dt,
                    'price': price,
                    'raw': r
                })
            except Exception as e:
                continue
                
        logger.info(f"Loaded {len(self.candles)} candles.")

    def run(self):
        logger.info("Running Replay...")
        
        for i, c in enumerate(self.candles):
            # Feed Strategy
            # Strategy.on_tick signature: on_tick(self, tick) -> but tick is dict.
            # Actually, looking at debug prints: TickEngine calls strategy.on_tick(tick)
            # In strategy.py: on_tick(self, tick). Extract Price: tick['lp']
            
            mock_tick = {'lp': c['price'], 'ft': c['ts']} # Mock tick structure
            
            # We must set strategy.last_signal_time internally? 
            # No, 'on_tick' returns a SIGNAL object or None.
            
            # Strategy.on_tick(price=..., timestamp=...)
            sig = self.strategy.on_tick(mock_tick['lp'], c['ts'])
            
            if sig:
                # Record Signal
                self.signals.append({
                    'index': i,
                    'time': c['ts'],
                    'price': c['price'],
                    'type': sig.type
                })
                
        logger.info(f"Replay Complete. Total Signals: {len(self.signals)}")

    def analyze(self):
        if not self.signals:
            logger.warning("No signs generated. Adjust threshold?")
            return

        logger.info("\n=== Backtest Performance Report ===")
        
        results = []
        
        # Forward Returns windows (minutes)
        windows = [5, 10, 30]
        
        for s in self.signals:
            idx = s['index']
            entry_price = s['price']
            sig_type = s['type']
            
            row = {'Time': s['time'], 'Type': sig_type, 'Price': entry_price}
            
            for w in windows:
                future_idx = idx + w
                if future_idx < len(self.candles):
                    future_price = self.candles[future_idx]['price']
                    change = future_price - entry_price
                    
                    # If BUY_CE, positive change is good.
                    # If BUY_PE, negative change is good.
                    if 'PE' in sig_type:
                        pnl_pts = -change
                    else:
                        pnl_pts = change
                        
                    row[f'{w}m_Pts'] = pnl_pts
                else:
                    row[f'{w}m_Pts'] = 0.0 # End of data
            
            results.append(row)
            
        df = pd.DataFrame(results)
        
        # Metrics
        print(df.to_string(index=False))
        print("\n--- Summary ---")
        
        for w in windows:
            col = f'{w}m_Pts'
            win_rate = (df[col] > 0).mean() * 100
            avg_pnl = df[col].mean()
            print(f"Window {w}m: Win Rate {win_rate:.1f}% | Avg Pts: {avg_pnl:.2f}")

if __name__ == "__main__":
    DATA_PATH = "data/history/banknifty_spot_m1.json"
    if not Path(DATA_PATH).exists():
        logger.error(f"Data not found at {DATA_PATH}. Run scripts/fetch_history.py first.")
        sys.exit(1)
        
    bt = SignalBacktester(DATA_PATH)
    bt.load_data()
    bt.run()
    bt.analyze()
