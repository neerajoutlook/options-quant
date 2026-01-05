import threading
import time
import random
import math
import logging
import pandas as pd
import os
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

class MarketSimulator:
    def __init__(self, token_map, callback, option_metadata=None, speed=1.0):
        self.token_map = token_map # Symbol -> Token
        self.callback = callback # Function(tick)
        self.option_metadata = option_metadata or {} # Token -> {type: 'CE'/'PE', strike: float, underlying: str}
        self.speed = speed
        self.running = False
        self.thread = None
        
        # Load Simulation Data
        self.data_file = os.path.join(os.path.dirname(__file__), "../data/simulation_history.csv")
        self.history_data = {} # Timestamp -> {Symbol -> Price}
        self.avail_timestamps = []
        
        # CRITICAL: Initialize prices dict BEFORE loading history
        self.prices = {}  # Token -> Current Price
        self.next_prices = {}  # Target Price for next minute
        self.open_prices = {}  # Track Open for UI
        self.prev_closes = {}  # Track PrevClose for UI
        
        self.use_history = self._load_history()
        
        # State
        self.current_idx = 0
        
        # Set defaults if history didn't populate prices
        self._initialize_defaults()

    def _load_history(self):
        """Load history CSV if available."""
        if not os.path.exists(self.data_file):
            logger.warning(f"⚠️ Simulation Data File not found: {self.data_file}. Fallback to Random Walk.")
            return False
            
        try:
            df = pd.read_csv(self.data_file)
            if df.empty: return False
            
            # Format: timestamp, symbol, price
            # Sort by timestamp first
            df.sort_values("timestamp", inplace=True)
            
            # Group by timestamp
            grouped = df.groupby('timestamp', sort=False)
            
            self.history_data = {}
            for ts, group in grouped:
                prices = dict(zip(group['symbol'], group['price']))
                self.history_data[ts] = prices
                
            self.avail_timestamps = list(self.history_data.keys()) # Already sorted
            logger.info(f"Loaded {len(self.avail_timestamps)} minutes of simulation data.")
            
            # --- INITIALIZE PRICES FROM FIRST RECORD ---
            if self.avail_timestamps:
                first_ts = self.avail_timestamps[0]
                first_prices = self.history_data[first_ts]
                
                # Update current prices map (Using token map)
                for sym, price in first_prices.items():
                    token = self.token_map.get(sym)
                    if token:
                        # Only set direct price if NOT an option
                        if token not in self.option_metadata:
                            self.prices[token] = price
                            # Set Open and PrevClose to this initial price to avoid jump artifacts
                            self.open_prices[token] = price
                            self.prev_closes[token] = price # Start with 0% change
                
                logger.info(f"Initialized Simulator Prices from {first_ts}")
                
            # --- FORCE INITIAL OPTION PRICING ---
            self._update_options()
            
            return True
        except Exception as e:
            logger.error(f"Error loading simulation data: {e}", exc_info=True)
            return False

    def _initialize_defaults(self):
        """Set initial prices for symbols not already loaded from history or live fetch."""
        cache_file = os.path.join(os.path.dirname(__file__), "../data/sim_base_prices.json")
        
        # If we already have prices from history, skip most of this
        if len(self.prices) > 0:
            logger.info(f"Skipping defaults - already have {len(self.prices)} prices from history")
            return
        
        # Index symbol mapping for Yahoo Finance
        index_symbols = {
            'BANKNIFTY': '^NSEBANK',
            'NIFTY': '^NSEI',
            'FINNIFTY': '^CNXFIN'
        }
        
        # Fallback prices (used if all else fails)
        fallback_prices = {
            'BANKNIFTY': 48000.0,
            'HDFCBANK': 1650.0,
            'ICICIBANK': 1050.0,
            'SBIN': 750.0,
            'AXISBANK': 1050.0,
            'KOTAKBANK': 1800.0,
            'INDUSINDBK': 1500.0,
            'NIFTY': 21500.0,
            'BANDHANBNK': 180.0,
            'FEDERALBNK': 150.0,
            'IDFCFIRSTB': 85.0,
            'PNB': 100.0,
            'AUBANK': 700.0
        }
        
        base_prices = {}
        
        # Try loading from cache first (if exists and is recent - today)
        cache_loaded = False
        if os.path.exists(cache_file):
            try:
                import json
                from datetime import date
                
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                cache_date = cached_data.get('date')
                today = date.today().isoformat()
                
                if cache_date == today:
                    base_prices = cached_data.get('prices', {})
                    cache_loaded = True
                    logger.info(f"📦 Loaded {len(base_prices)} cached base prices from {cache_date}")
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")
        
        # If cache not loaded, fetch live prices
        if not cache_loaded:
            logger.info("📡 Fetching live reference prices (once) from Yahoo Finance...")
            
            try:
                import yfinance as yf
                import json
                from datetime import date
                
                # Get all symbols from token_map
                all_symbols = list(self.token_map.keys())
                
                for sym in all_symbols:
                    # Skip option symbols
                    if any(char.isdigit() for char in sym) or 'CE' in sym or 'PE' in sym:
                        continue
                    
                    try:
                        # Determine Yahoo Finance symbol
                        if sym in index_symbols:
                            yf_sym = index_symbols[sym]
                        else:
                            yf_sym = f"{sym}.NS"
                        
                        ticker = yf.Ticker(yf_sym)
                        hist = ticker.history(period='1d')
                        if not hist.empty:
                            live_price = hist['Close'].iloc[-1]
                            base_prices[sym] = round(live_price, 2)
                            logger.info(f"✅ {sym}: ₹{live_price:.2f}")
                    except Exception as e:
                        logger.debug(f"Could not fetch {sym}: {e}")
                
                logger.info(f"Fetched {len(base_prices)} live prices")
                
                # Save to cache
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, 'w') as f:
                    json.dump({
                        'date': date.today().isoformat(),
                        'prices': base_prices
                    }, f, indent=2)
                logger.info(f"💾 Cached base prices to {cache_file}")
                
            except Exception as e:
                logger.warning(f"Live price fetch failed: {e}. Using fallbacks.")
        
        # Fill missing symbols with fallbacks
        for sym in self.token_map.keys():
            if sym not in base_prices and sym in fallback_prices:
                base_prices[sym] = fallback_prices[sym]
                logger.info(f"⚠️ {sym}: ₹{fallback_prices[sym]:.2f} (Fallback)")
            elif sym not in base_prices and not any(char.isdigit() for char in sym):
                base_prices[sym] = 1000.0
        
        # Map to tokens (only if not already set)
        for sym, price in base_prices.items():
            if sym in self.token_map:
                token = self.token_map[sym]
                if token not in self.prices:  # Don't overwrite history prices
                    self.prices[token] = price
                    self.open_prices[token] = price
                    self.prev_closes[token] = price

    def _calculate_option_price(self, spot, strike, otype, time_to_expiry_years=0.01):
        """
        Calculate Option Price (Intrinsic + Time Value).
        Using a simplified model for stability.
        """
        try:
            # Intrinsic
            if otype == 'CE':
                intrinsic = max(0, spot - strike)
            else: # PE
                intrinsic = max(0, strike - spot)
            
            # Time Value Approximation
            # Max time value at ATM, decays as we move away
            dist_pct = abs(spot - strike) / spot
            
            # Base Time Value (e.g. 1% of spot for ATM at 7 DTE)
            # Adjust based on 'time_to_expiry_years' (linear decay for Sim)
            # A rough heuristic: ATM Option ~ 0.5-1.0% of Spot per week of time
            
            base_tv_pct = 0.006 # 0.6% of spot (~300 pts for BN)
            
            # Decay with distance (Bell curve-ish)
            tv_decay = math.exp(-200 * (dist_pct ** 2)) # Rapid decay
            
            time_value = spot * base_tv_pct * tv_decay
            
            # Random Noise for realism (IV fluctuation)
            noise = random.uniform(-0.02, 0.02) * time_value
            
            price = intrinsic + time_value + noise
            return round(max(0.05, price), 2)
        except:
            return 0.0

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        mode = "Historical Replay" if self.use_history else "Random Walk"
        logger.info(f"🚀 Market Simulator Started ({mode}, Speed: {self.speed}x)")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Market Simulator Stopped")
        
    def _run_loop(self):
        # Base Time: Map first history timestamp to NOW
        start_time_wall = datetime.now(IST)
        
        while self.running:
            try:
                if self.use_history and self.current_idx < len(self.avail_timestamps) - 1:
                    # REPLAY MODE
                    self._process_replay_step()
                else:
                    # RANDOM WALK / DONE
                    if self.use_history and self.current_idx >= len(self.avail_timestamps) - 1:
                        # Reset loop or just randomly walk from last price?
                        # Let's random walk from last known prices
                        self._process_random_walk_step()
                    else:
                        self._process_random_walk_step()
                        
                # Sleep based on speed (Ticks per second)
                # We want continuous flow, so sleep small amount
                time.sleep(0.5 / self.speed) # e.g. 2 ticks per second at 1x
                
            except Exception as e:
                logger.error(f"Simulator Error: {e}", exc_info=True)
                time.sleep(1)

    def _process_replay_step(self):
        """Interpolate between current minute and next minute of history."""
        # Current Minute Stats
        curr_ts_str = self.avail_timestamps[self.current_idx]
        next_ts_str = self.avail_timestamps[self.current_idx + 1]
        
        curr_data = self.history_data[curr_ts_str]
        next_data = self.history_data[next_ts_str]
        
        # On first loading of a new minute, set target
        # We need state tracking for interpolation
        # Simplified: Just Brownian Bridge towards next target
        
        # 1. Update Underlying Prices
        for symbol, next_price in next_data.items():
            current_price = self.prices.get(self.token_map.get(symbol), next_price) # Get current state or default
            token = self.token_map.get(symbol)
            if not token: continue # Symbol not mapped
            
            # Interpolation Logic
            # Move 10% towards target + Random Noise
            diff = next_price - current_price
            
            # If very close, just snap? No, let it drift.
            step = diff * 0.05 # Move 5% of the gap (slower convergence)
            
            # Reduce noise here too (0.01% instead of 0.05%)
            noise = random.gauss(0, next_price * 0.0001) 
            
            new_price = current_price + step + noise
            self.prices[token] = new_price
            
            self._emit_tick(token, new_price)
            
        # 2. Update Options
        self._update_options()
        
        # 3. Advance Time Logic
        # We need to stay on this "Minute" for some duration?
        # Simpler: Just rely on the loop speed. 
        # Ideally we want to consume 1 minute of data in (60 / speed) seconds.
        # But for UI "fluctuation" it's better to just stream.
        
        # Randomly advance index to move through data
        # If we loop fast (0.5s), we advance every ~120 iterations for 1 min?
        # Let's use a counter or probability
        if random.random() < (0.05 * self.speed): # Chance to advance minute
            self.current_idx += 1
            if self.current_idx >= len(self.avail_timestamps) - 1:
                logger.info("🔁 Replay Loop restarting/finished")
                # self.current_idx = 0 # Loop? Or stop?
                # Let's stick to last price (Random walk will take over)

    def _process_random_walk_step(self):
        """Fallback random walk."""
        for symbol, token in self.token_map.items():
            if token in self.option_metadata: continue
            
            curr_price = self.prices.get(token, 1000.0)
            
            # Use smaller drift and much smaller sigma for smoother ticks
            # Drift: ±0.01% bias
            drift = random.uniform(-0.0001, 0.0001)
            
            # Sigma: 0.01% volatility per tick (was 0.05%)
            # At 1x speed (2 ticks/sec), this matches roughly 1% daily volatility
            sigma = 0.0001 
            
            shock = random.gauss(0, sigma)
            
            # Use geometric change
            change_pct = drift + shock
            new_price = curr_price * (1 + change_pct)
            
            self.prices[token] = new_price
            self._emit_tick(token, new_price)
            
        self._update_options()

    def _update_options(self):
        """Recalculate all option prices based on current Spot prices."""
        current_time = datetime.now(IST)
        
        for token, meta in self.option_metadata.items():
            underlying_sym = meta.get('underlying')
            underlying_token = self.token_map.get(underlying_sym)
            
            if underlying_token and underlying_token in self.prices:
                spot = self.prices[underlying_token]
                strike = meta.get('strike')
                otype = meta.get('type')
                
                # Calculate Price
                new_price = self._calculate_option_price(spot, strike, otype)
                self.prices[token] = new_price
                
                self._emit_tick(token, new_price)

    def _emit_tick(self, token, price, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now(IST)
        
        # Initialize Open/PrevCLose logic
        if token not in self.open_prices:
            self.open_prices[token] = price
            # Assume PrevClose was slightly different to show "Change"
            # Or just set it to Price so Change is 0 initially
            self.prev_closes[token] = price 
            
        open_price = self.open_prices[token]
        prev_close = self.prev_closes[token]
        change = price - prev_close
        
        tick = {
            't': 'tk',
            'e': 'NSE',
            'tk': token,
            'lp': str(round(price, 2)),
            'v': str(int(random.random() * 500)), # Random tick volume
            'c': str(round(change, 2)), # Change from Prev Close
            'o': str(round(open_price, 2)), # Open
            'h': str(round(max(open_price, price), 2)), # High (Approx)
            'l': str(round(min(open_price, price), 2)), # Low (Approx)
            'ft': timestamp.timestamp(),
            'bp1': str(round(price * 0.9995, 2)),
            'sp1': str(round(price * 1.0005, 2))
        }
        self.callback(tick)
