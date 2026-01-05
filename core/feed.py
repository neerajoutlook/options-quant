import logging
import time
from datetime import datetime, timedelta
from typing import Dict
import re
import threading
import asyncio
import pytz
import pandas as pd

from core.shoonya_client import ShoonyaSession
from core.candles import CandleResampler
from core.strategy import Strategy, WeightageCalculator, TechnicalIndicators
from core.telegram_bot import TelegramBot
from core import config
from core.order_logger import log_signal, log_order_attempt, log_order_result, log_order_update
from core.paper_trading import PaperTradingEngine
from core.market_data import market_data

# OMS Imports
from core.oms.position_manager import PositionManager
from core.oms.order_manager import OrderManager

logger = logging.getLogger(__name__)

# Timezone Definition
IST = pytz.timezone('Asia/Kolkata')

class TickEngine:
    def __init__(self):
        self.shoonya = ShoonyaSession()
        self.telegram = TelegramBot()
        
        self.resampler_3m = CandleResampler(interval_minutes=3)
        self.resampler_5m = CandleResampler(interval_minutes=5)
        
        self.weightage_calc = WeightageCalculator(use_volume=config.USE_VOLUME_WEIGHTING)
        self.strategy = Strategy(
            self.weightage_calc,
            min_strength=config.MIN_SIGNAL_STRENGTH,
            min_hold_time=config.MIN_SIGNAL_HOLD_TIME
        )
        
        # OMS Initialization
        self.position_manager = PositionManager()
        self.order_manager = OrderManager(self.shoonya, self.position_manager)
        
        self.paper_trading = PaperTradingEngine()
        
        self.token_map: Dict[str, str] = {} # Symbol -> Token
        self.reverse_token_map: Dict[str, str] = {} # Token -> Symbol
        
        from core.instruments import InstrumentManager
        self.instrument_mgr = InstrumentManager()
        self.tracked_atms: Dict[str, float] = {} # Symbol -> Current ATM Strike
        self.vwap_map = {} # Symbol -> {cum_vol, cum_pv, last_vol}
        self.tracked_stocks = set() # Set of underlying symbols to track for ATMs
        self.macro_data = {} # Symbol -> {trend, rsi, message}
        
        # Order tracking
        self.current_order_id: str = None
        self.current_symbol: str = None
        self.current_entry_price = None  # Track entry price for P&L
        
        self.running = False
        self.offline = False  # Offline mode flag


    def initialize(self):
        """Login and resolve tokens."""
        logger.info(f"Initializing TickEngine...")
        
        # Login
        try:
            self.shoonya.login()
        except Exception as e:
            logger.error(f"Login failed (Switching to OFFLINE mode): {e}")
            self.offline = True
            
        if self.offline:
            logger.warning("⚠️ SYSTEM RUNNING IN OFFLINE MODE (No Live Feed) ⚠️")

        # Load master contract
        
        # Resolve Tokens for Bank Nifty Constituents
        logger.info("Resolving tokens...")
        from core.strategy import BANKNIFTY_WEIGHTS
        
        # Hardcoded tokens for fallback/offline
        # from core.instruments import HARDCODED_TOKENS 
        # (Assuming we might not have this file, let's hardcode locally for now)
        FALLBACK_BANKNIFTY = '26009'
        FALLBACK_HDFCBANK = '1333'
        
        if self.offline:
            # Populate with fallback tokens
            self.token_map['BANKNIFTY'] = FALLBACK_BANKNIFTY
            self.reverse_token_map[FALLBACK_BANKNIFTY] = 'BANKNIFTY'
            self.token_map['HDFCBANK'] = FALLBACK_HDFCBANK
            self.reverse_token_map[FALLBACK_HDFCBANK] = 'HDFCBANK'
            logger.info("Offline Mode: using hardcoded tokens.")
            return

        for symbol in BANKNIFTY_WEIGHTS.keys():
            # Search NSE Equity
            ret = self.shoonya.search_scrip(exchange="NSE", searchstr=symbol)
            if ret and ret.get('stat') == 'Ok' and ret.get('values'):
                # Find exact match by symname or tsym
                token = None
                for result in ret['values']:
                    if result.get('symname') == symbol or result.get('tsym') == f"{symbol}-EQ":
                        token = result['token']
                        break
                
                if token:
                    self.token_map[symbol] = token
                    self.reverse_token_map[token] = symbol
                    self.tracked_stocks.add(symbol) # Mark as underlying for ATM tracking
                    logger.info(f"Resolved {symbol} -> {token}")
                else:
                    logger.error(f"Could not find exact match for {symbol} in results: {ret['values']}")
            else:
                logger.error(f"Could not resolve token for {symbol}") 

        # Resolve Bank Nifty Index Token (NSE Index)
        ret = self.shoonya.search_scrip(exchange="NSE", searchstr="BANKNIFTY")
        banknifty_found = False
        if ret and ret.get('stat') == 'Ok' and ret.get('values'):
            for item in ret['values']:
                # Look for the index, not futures or ETFs
                if item.get('instname') == 'UNDIND' or 'NIFTY BANK' in item.get('cname', ''):
                    token = item['token']
                    self.token_map["BANKNIFTY"] = token
                    self.reverse_token_map[token] = "BANKNIFTY"
                    logger.info(f"Resolved BANKNIFTY -> {token}")
                    banknifty_found = True
                    break
        
        # Fallback to hardcoded token if search fails
        if not banknifty_found:
            logger.warning("Search failed for BANKNIFTY, using hardcoded token 26009")
            token = "26009"  # NSE Bank Nifty index token
            self.token_map["BANKNIFTY"] = token
            self.reverse_token_map[token] = "BANKNIFTY"
            logger.info(f"Resolved BANKNIFTY -> {token} (hardcoded)")
        
        # DEBUG: Check Singleton
        from core.market_data import market_data
        logger.info(f"DEBUG: feed.py market_data ID: {id(market_data)}")
        try:
            with open("debug_feed_id.txt", "w") as f:
                f.write(str(id(market_data)))
        except:
            pass
        
        # Ensure BANKNIFTY is in tracked stocks for seeding
        if "BANKNIFTY" in self.token_map:
            self.tracked_stocks.add("BANKNIFTY")

        if "BANKNIFTY" not in self.token_map:
             logger.error("Could not resolve BANKNIFTY token!")

    def start(self):
        """Start the WebSocket feed and strategy loop."""
        self.running = True
        
        # Subscribe List
        instruments = []
        for symbol, token in self.token_map.items():
            # Bank Nifty is on NSE, constituents are also on NSE
            exchange = "NSE"
            instruments.append(f"{exchange}|{token}")
            
        logger.info(f"Subscribing to {len(instruments)} instruments: {instruments}")

        # Seed History (Fetch data from 9:15 AM today to calculate VWAP)
        try:
            self._seed_history()
        except Exception as e:
            logger.error(f"Seeding history failed: {e}", exc_info=True)
        
        # Fetch Macro Data (Background update)
        threading.Thread(target=self._update_macro_data).start()
        
        def on_ws_connect():
            # Small delay to ensure WebSocket is fully ready
            time.sleep(0.5)
            logger.info("WebSocket ready, subscribing to instruments...")
            self.shoonya.subscribe(instruments)
        
        self.shoonya.start_websocket(
            on_ticks=self.on_tick,
            on_orders=self.on_order_update,
            on_connect=on_ws_connect
        )
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        self.shoonya.close_websocket()
        logger.info("TickEngine stopped.")

    def on_tick(self, tick: dict):
        """Handle incoming tick."""
        # tick format: {'t': 'tk', 'e': 'NSE', 'tk': '1234', 'lp': '100.5', 'v': '1000', ...}
        token = tick.get('tk')
        if not token:
            return
            
        symbol = self.reverse_token_map.get(token)
        if not symbol:
            return
            
        price = float(tick.get('lp', 0))
        volume = int(tick.get('v', 0)) # This might be cumulative volume
        timestamp = datetime.now(IST) # Use IST
        
        if price == 0:
            return

        # Update VWAP Stats
        if symbol not in self.vwap_map:
             self.vwap_map[symbol] = {'cum_vol': 0, 'cum_pv': 0}
        
        # Calculate Tick Volume (naive difference)
        # Note: 'v' in tick is usually cumulative for the day
        current_vol = int(tick.get('v', 0))
        if current_vol > 0:
             last_vol = self.vwap_map[symbol].get('last_vol', 0)
             if current_vol > last_vol:
                 vol_delta = current_vol - last_vol
                 self.vwap_map[symbol]['cum_vol'] += vol_delta
                 self.vwap_map[symbol]['cum_pv'] += (price * vol_delta)
                 self.vwap_map[symbol]['last_vol'] = current_vol
        
        # Calculate VWAP
        vwap = price # Default to current price if no volume
        if self.vwap_map[symbol]['cum_vol'] > 0:
             vwap = self.vwap_map[symbol]['cum_pv'] / self.vwap_map[symbol]['cum_vol']

        # Determine Trend
        trend = "NEUTRAL"
        if price > vwap:
             trend = "BULLISH"
        elif price < vwap:
             trend = "BEARISH"

        # --- WEB DASHBOARD UPDATE ---
        try:
            # Import here to avoid circular dependencies if any
            from core.market_data import market_data
            
            # Prepare data payload
            change = 0.0
            if 'c' in tick:
                change = float(tick['c'])
            elif 'o' in tick:
                change = price - float(tick['o'])
                
            payload = {
                'symbol': symbol,
                'ltp': price,
                'volume': volume,
                'open': float(tick.get('o', 0)),
                'high': float(tick.get('h', 0)),
                'low': float(tick.get('l', 0)),
                'change': change,
                'vwap': vwap,
                'change': change,
                'vwap': vwap,
                'trend': trend,
                'macro': self.macro_data.get(symbol, {}),
                'timestamp': datetime.now().isoformat()
            }
            
            # Fire-and-forget update
            if hasattr(market_data, 'latest_prices'):
                market_data.latest_prices[symbol] = payload
        except Exception:
            pass
        # ----------------------------

        # --- ATM OPTION TRACKING (Bank Nifty Constituents) ---
        # Only run for tracked UNDERLYING stocks, not for options themselves
        if symbol in self.tracked_stocks: 
            self._check_atm_subscription(symbol, price)

        # Update Weightage Calculator
        if symbol != "BANKNIFTY" and symbol in self.tracked_stocks:
             # We assume 'o' (Open) is available in the tick or captured earlier
             # (Logic for weightage calc only needs stocks)
            if 'o' in tick:
                self.weightage_calc.update_data(symbol, price, volume, is_open=True)
            else:
                self.weightage_calc.update_data(symbol, price, volume)

        # Update Bank Nifty Candles & Run Strategy
        if symbol == "BANKNIFTY":
            # Update Resamplers
            c3 = self.resampler_3m.process_tick(price, volume, timestamp)
            c5 = self.resampler_5m.process_tick(price, volume, timestamp)
            
            if c3:
                logger.info(f"3-min Candle Closed: {c3}")
            if c5 and c5.complete:
                logger.info(f"5-min Candle Closed: {c5}")
            
            # Calculate weighted strength
            strength = self.weightage_calc.calculate_weighted_strength()
            
            # Run Strategy
            signal = self.strategy.on_tick(price, timestamp.timestamp())
            
            if signal:
                logger.info(f"SIGNAL GENERATED: {signal}")
                
                # Log signal to orders log
                log_signal(signal.type, signal.symbol, signal.price, strength, signal.reason)
                
                self.telegram.send_message(
                    f"📊 **Signal: {signal.type}**\n"
                    f"Price: {signal.price:.2f}\n"
                    f"Reason: {signal.reason}"
                )
                
                # Execute the signal
                self.execute_signal(signal)
            else:
                self.weightage_calc.update_data(symbol, price, volume)

    def _check_atm_subscription(self, symbol: str, ltp: float):
        """Check and subscribe to ATM options if strike changed"""
        if not hasattr(self, 'instrument_mgr'):
            return

        # Simple throttling/hysteresis could be added here
        # For now, calculate ATM
        atm_strike = self.instrument_mgr.calculate_atm_strike(symbol, ltp)
        
        # Check if we are already subscribed to this ATM
        current_atm = self.tracked_atms.get(symbol)
        
        if current_atm != atm_strike:
            logger.info(f"ATM Shift {symbol}: {current_atm} -> {atm_strike} (LTP: {ltp})")
            
            # Find tokens for CE and PE at this strike
            # We need to run this in background or it will block tick processing?
            # Shoonya search is blocking/HTTP. Ideally run in separate thread or queue.
            # For PoC, we'll try to do it via a quick lookup if we have the cache, 
            # otherwise queue it.
            
            # For this step, let's just Log it to verify calculation is working
            # Implementing full robust dynamic subscription requires thread management
            self.tracked_atms[symbol] = atm_strike
            
            # Trigger background subscription task
            threading.Thread(target=self._subscribe_atm_options, args=(symbol, atm_strike)).start()

    def _subscribe_atm_options(self, symbol: str, strike: float):
        """Find and subscribe to ATM options (Local Lookup)"""
        try:
            logger.info(f"🔎 Lookup options for {symbol} {strike}")
            
            # Use new local lookup
            options = self.instrument_mgr.get_atm_option_tokens(symbol, strike)
            
            if options:
                # Subscribe CE
                if 'CE' in options:
                    ce = options['CE']
                    token = ce['token']
                    tsym = ce['tsym']
                    logger.info(f"✅ Subscribing CE: {tsym} ({token})")
                    self.shoonya.subscribe(f'NFO|{token}')
                    self.token_map[tsym] = token
                    self.reverse_token_map[token] = tsym
                    
                # Subscribe PE
                if 'PE' in options:
                    pe = options['PE']
                    token = pe['token']
                    tsym = pe['tsym']
                    logger.info(f"✅ Subscribing PE: {tsym} ({token})")
                    self.shoonya.subscribe(f'NFO|{token}')
                    self.token_map[tsym] = token
                    self.reverse_token_map[token] = tsym
            else:
                logger.warning(f"No options found in master file for {symbol} {strike}")

        except Exception as e:
            logger.error(f"ATM Sub Error {symbol}: {e}")


    def _seed_history(self):
        """Fetch historical data to populate 'latest_prices' before first tick."""
        logger.info("⏳ Seeding history for VWAP calculation...")
        try:
            now_ist = datetime.now(IST)
            start_of_day = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
            
            # Fetch last 3 days to ensure we have data for UI even on Monday mornings
            # But only calculate VWAP for TODAY
            # But only calculate VWAP for TODAY
            from datetime import timedelta
            search_start_time = now_ist - timedelta(days=3)
            start_ts = search_start_time.timestamp()

            for symbol in self.tracked_stocks:
                token = self.token_map.get(symbol)
                if not token: continue

                logger.info(f"Downloading history for {symbol}...")
                history = self.shoonya.get_history(exchange="NSE", token=token, start_time=start_ts, interval=1)
                
                if history and isinstance(history, list):
                    # Process candles chronologically
                    history.sort(key=lambda x: x.get('time', ''))
                    
                    cum_vol = 0
                    cum_pv = 0.0
                    
                    # VWAP Calculation (Strictly Today)
                    for candle in history:
                         candle_time_str = candle.get('time', '') # Format: 'dd-MM-yyyy HH:mm:ss'
                         # Parse time if needed, or simplistically: 
                         # Shoonya returns time as string. 
                         # For now, let's assume if it matches today's date string?
                         # Simpler: just use all history if it's today, otherwise filter.
                         # Given robustness need: Let's calc VWAP from ALL returned history? 
                         # NO, VWAP must be intraday.
                         
                         # Check if candle is from today
                         try:
                             c_time = datetime.strptime(candle_time_str, "%d-%m-%Y %H:%M:%S").replace(tzinfo=IST)
                             if c_time >= start_of_day:
                                 c = float(candle.get('intc', 0))
                                 v = int(candle.get('intv', 0))
                                 if v > 0:
                                     cum_vol += v
                                     cum_pv += (c * v)
                         except:
                             pass # validation error, skip
                    
                    # Update Map
                    if symbol not in self.vwap_map:
                         self.vwap_map[symbol] = {'cum_vol': 0, 'cum_pv': 0, 'last_vol': cum_vol}
                    
                    if cum_vol > 0:
                        self.vwap_map[symbol]['cum_vol'] = cum_vol
                        self.vwap_map[symbol]['cum_pv'] = cum_pv
                    
                    # --- POPULATE INITIAL UI DATA (Use LAST available candle) ---
                    if history:
                        last_candle = history[-1] # Get last available candle (even if yesterday)
                        close_price = float(last_candle.get('intc', 0))
                        
                        logger.info(f"DEBUG: Seeding {symbol} with close_price={close_price}")

                        # Fake payload to initialize UI
                        payload = {
                            'symbol': symbol,
                            'ltp': close_price,
                            'volume': int(last_candle.get('intv', 0)),
                            'open': float(last_candle.get('into', 0)),
                            'high': float(last_candle.get('inth', 0)),
                            'low': float(last_candle.get('intl', 0)),
                            'change': 0.0, 
                            'vwap': close_price,
                            'trend': 'NEUTRAL',
                            'macro': {},
                            'timestamp': datetime.now(IST).isoformat()
                        }
                        
                        from core.market_data import market_data
                        if hasattr(market_data, 'latest_prices'):
                            market_data.latest_prices[symbol] = payload
                    else:
                        logger.warning(f"DEBUG: No history for {symbol} - UI will be empty")
                    # ------------------------------------------------------------------

                    # Update current VWAP for logging
                    if self.vwap_map[symbol].get('cum_vol', 0) > 0:
                        vwap = self.vwap_map[symbol]['cum_pv'] / self.vwap_map[symbol]['cum_vol']
                        logger.info(f"SEED {symbol}: VWAP={vwap:.2f}, Vol={cum_vol}")
                else:
                    logger.warning(f"DEBUG: History API returned empty/invalid for {symbol}: {history}")


        except Exception as e:
            logger.error(f"Error seeding history: {e}", exc_info=True)
            
        # FINAL FALLBACK: If BANKNIFTY is missing from UI, force dummy data
        from core.market_data import market_data
        if 'BANKNIFTY' not in market_data.latest_prices:
            logger.warning("⚠️ FORCE SEEDING BANKNIFTY DUMMY DATA (API Failed) ⚠️")
            market_data.latest_prices['BANKNIFTY'] = {
                'symbol': 'BANKNIFTY',
                'ltp': 51500.0, 'change': 150.0, 'percent_change': 0.29,
                'open': 51400.0, 'high': 51600.0, 'low': 51300.0, 'close': 51350.0,
                'volume': 1000000,
                'vwap': 51500.0,
                'trend': 'NEUTRAL',
                'macro': {},
                'timestamp': datetime.now(IST).isoformat()
            }

    def _update_macro_data(self):
        """Fetch 30-day hourly history for macro trend analysis."""
        logger.info("🌊 Fetching Macro Data (30-Day Hourly)...")
        try:
            now = datetime.now(IST)
            start_time = now - timedelta(days=30)
            
            for symbol in self.tracked_stocks:
                token = self.token_map.get(symbol)
                if not token: continue
                
                # Fetch hourly (interval=60)
                # Shoonya usually returns dicts in list
                history = self.shoonya.get_history(exchange="NSE", token=token, 
                                                 start_time=start_time.timestamp(), 
                                                 interval="60")
                
                if history and isinstance(history, list):
                     # Convert to DataFrame for TechnicalIndicator
                     df = pd.DataFrame(history)
                     # Needs 'close' column
                     df['close'] = pd.to_numeric(df['intc'])
                     # Optional: Needs 'timestamp' if we care about sort, usually sorted or sort by 'time'
                     
                     indicators = TechnicalIndicators.calculate_macro_trend(df)
                     self.macro_data[symbol] = indicators
                     logger.info(f"MACRO {symbol}: {indicators}")
                     
                     # Throttle slightly
                     time.sleep(0.5)
                else:
                    logger.warning(f"No macro history for {symbol}")
                    
        except Exception as e:
             logger.error(f"Macro Data Error: {e}")

    def on_order_update(self, data):
        """Handle order updates from WebSocket"""
        logger.info(f"Order Update: {data}")
        
        # Log to orders file
        order_id = data.get('norenordno', 'N/A')
        symbol = data.get('tsym', 'N/A')
        status = data.get('status', 'N/A')
        rejection_reason = data.get('rejreason', '')
        
        additional_info = f"Rejection: {rejection_reason}" if rejection_reason and rejection_reason.strip() else ""
        log_order_update(order_id, symbol, status, additional_info)
        
        self.telegram.send_message(f"📊 Order Update: {data.get('status', 'N/A')}")
        
    def place_manual_order(self, symbol: str, side: str, qty: int, price: float = 0.0):
        """
        Handle Manual Order from UI
        """
        logger.info(f"Manual Order Request: {side} {qty} {symbol} @ {price}")
        
        # Delegate to OMS
        order_id = self.order_manager.place_order(symbol, side, qty, "MANUAL")
        
        if order_id:
            msg = f"✅ Manual Order Placed: {side} {qty} {symbol} (ID: {order_id})"
            # self.send_telegram(msg) # Optional
            
            # Temporary: Updating Position Manager directly for UI feedback (Simulated Fill)
            # In real system, this happens on socket callback
            ltp = market_data.latest_prices.get(symbol, {}).get('ltp', 0.0)
            if ltp > 0:
                 self.position_manager.on_fill(symbol, qty, ltp, side)
            
            return {"status": "success", "order_id": order_id}
        else:
            return {"status": "error", "message": "Order Placement Failed"}
            
                

    def execute_signal(self, signal):
        """Execute the signal by placing an order for Bank Nifty options."""
        logger.info(f"EXECUTING {signal.type} @ {signal.price}")
        
        # Get current Bank Nifty price
        current_price = signal.price
        
        # Calculate weighted strength for strike selection
        strength = abs(self.weightage_calc.calculate_weighted_strength())
        
        # Smart Strike Selection based on signal strength
        # Goal: ~50% probability (Delta ~0.5) with leverage on strong signals
        
        base_atm = round(current_price / 100) * 100  # ATM strike
        
        if signal.type in ["BUY_CE", "BUY_PE"]:
            # For entry signals, select strike based on strength
            if strength > 8.0:
                # Very strong signal: Go 2 strikes OTM for better leverage
                # Delta ~0.40-0.45, probability ~45%
                offset = 200
            elif strength > 6.5:
                # Strong signal: Go 1 strike OTM
                # Delta ~0.45-0.48, probability ~47%
                offset = 100
            else:
                # Moderate signal: ATM for higher probability
                # Delta ~0.50, probability ~50%
                offset = 0
            
            # Apply offset in correct direction
            if "CE" in signal.type:
                strike = base_atm + offset  # OTM Call above current price
            else:
                strike = base_atm - offset  # OTM Put below current price
                
            logger.info(f"Strike Selection: Strength={strength:.2f}, Base ATM={base_atm}, Offset={offset}, Selected={strike}")
        else:
            # For EXIT, use same strike we entered (stored in current_symbol)
            # Extract strike from stored symbol
            if self.current_symbol and "BANKNIFTY" in self.current_symbol:
                # Extract strike from symbol like "BANKNIFTY30DEC25C59600"
                match = re.search(r'[CP](\d+)$', self.current_symbol)
                if match:
                    strike = int(match.group(1))
                    logger.info(f"EXIT using entry strike: {strike}")
                else:
                    strike = base_atm
                    logger.warning("Could not extract strike from stored symbol, using ATM")
            else:
                strike = base_atm
                logger.warning("No stored symbol for exit, using ATM")
        
        # Determine option type  (C for Call, P for Put - NOT CE/PE!)
        option_type = "C" if "CE" in signal.type else "P"
        
        # Get current month's expiry date (last Wednesday)
        import calendar
        
        today = datetime.now()
        year = today.year
        month = today.month
        
        # Find last Wednesday of current month
        # Get number of days in month
        last_day = calendar.monthrange(year, month)[1]
        
        # Check each day from end of month backwards
        for day in range(last_day, 0, -1):
            date = datetime(year, month, day)
            if date.weekday() == 2:  # Wednesday is 2
                expiry_date = date
                break
        
        # If today is after monthly expiry, get next month's expiry
        if today > expiry_date or (today.date() == expiry_date.date() and today.hour >= 15):
            # Move to next month
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            
            last_day = calendar.monthrange(year, month)[1]
            for day in range(last_day, 0, -1):
                date = datetime(year, month, day)
                if date.weekday() == 2:
                    expiry_date = date
                    break
        
        # Format: BANKNIFTY25DEC24C51500 (use C/P not CE/PE!)
        expiry_str = expiry_date.strftime("%d%b%y").upper()
        
        # Construct symbol name for Bank Nifty
        symbol = f"BANKNIFTY{expiry_str}{option_type}{strike}"
        
        logger.info(f"Attempting to trade: {symbol}")
        
        # Determine action
        action = "S" if signal.type == "EXIT" else "B"
        qty = config.QUANTITY
        
        # Log order attempt
        log_order_attempt(action, symbol, qty, strike)
        
        # === PAPER TRADING MODE ===
        if config.PAPER_TRADING_MODE:
            if signal.type in ["BUY_CE", "BUY_PE"]:
                # Paper entry
                self.paper_trading.enter_position(signal.type, signal.price, strike, qty, signal.reason)
                self.current_entry_price = signal.price
                
                msg = (
                    f"📝 PAPER ENTRY\n"
                    f"Symbol: {symbol}\n"
                    f"Action: {action} {qty} lots\n"
                    f"Type: {signal.type}\n"  
                    f"Price: ₹{signal.price:.2f}\n"
                    f"Strike: {strike}\n"
                    f"Strength: {strength:.2f}"
                )
            else:
                # Paper exit
                pnl = self.paper_trading.exit_position(signal.price, signal.reason)
                pnl_display = f"₹{pnl:.2f}" if pnl else "N/A"
                pnl_emoji = "💚" if pnl and pnl > 0 else "❌" if pnl and pnl < 0 else "⚪"
                
                msg = (
                    f"📝 {pnl_emoji} PAPER EXIT\n"
                    f"Symbol: {symbol}\n"
                    f"Action: SELL {qty} lots\n"
                    f"Exit Price: ₹{signal.price:.2f}\n"
                    f"Entry Price: ₹{self.current_entry_price:.2f}\n"
                    f"P&L: {pnl_display}"
                )
                self.current_entry_price = None
            
            logger.info(msg)
            self.telegram.send_message(msg)
            return  # Don't place real orders in paper mode
        
        # === REAL TRADING MODE ===
        try:
            order_id = self.shoonya.place_order(
                buy_or_sell=action,
                product_type="M",
                exchange="NFO",
                tradingsymbol=symbol,
                quantity=qty,
                discloseqty=0,
                price_type="MKT",  # Market order
                price=0,
                trigger_price=None,
                retention="DAY",
                remarks=f"Auto-{signal.type}"
            )
            
            if order_id:
                # Track position and send detailed alert
                if signal.type in ["BUY_CE", "BUY_PE"]:
                    # Entry - we don't know exact fill price yet, use signal price as estimate
                    entry_price_estimate = signal.price
                    self.current_entry_price = entry_price_estimate
                    
                    # Open position in tracker
                    self.position_tracker.open_position(
                        symbol=symbol,
                        entry_price=entry_price_estimate,
                        quantity=qty,
                        order_id=order_id
                    )
                    
                    msg = (
                        f"✅ **ENTRY ORDER PLACED**\n"
                        f"Symbol: `{symbol}`\n"
                        f"Action: **{action}** {qty} lots\n"
                        f"Type: {signal.type}\n"
                        f"Entry Price (est): ₹{entry_price_estimate:.2f}\n"
                        f"Strike: {strike}\n"
                        f"Order ID: {order_id}"
                    )
                else:
                    # Exit - calculate P&L
                    exit_price_estimate = signal.price
                    pnl = self.position_tracker.close_position(
                        exit_price=exit_price_estimate,
                        order_id=order_id
                    )
                    
                    pnl_display = f"₹{pnl:.2f}" if pnl else "N/A"
                    pnl_emoji = "💚" if pnl and pnl > 0 else "❌" if pnl and pnl < 0 else "⚪"
                    
                    msg = (
                        f"{pnl_emoji} **EXIT ORDER PLACED**\n"
                        f"Symbol: `{symbol}`\n"
                        f"Action: **SELL** {qty} lots\n"
                        f"Exit Price (est): ₹{exit_price_estimate:.2f}\n"
                        f"Entry Price (est): ₹{self.current_entry_price:.2f}\n"
                        f"**P&L: {pnl_display}**\n"
                        f"Order ID: {order_id}"
                    )
                    
                    self.current_entry_price = None
                
                logger.info(msg)
                log_order_result(order_id, symbol, qty, "PLACED")
                self.telegram.send_message(msg)
                
                # Track order for exit logic
                self.current_order_id = order_id
                self.current_symbol = symbol
            else:
                # Order failed - send detailed error message
                strength = abs(self.weightage_calc.calculate_weighted_strength())
                
                msg = (
                    f"❌ **ORDER FAILED**\n"
                    f"Symbol: `{symbol}`\n"
                    f"Type: {signal.type}\n"
                    f"Action: **{action}** {qty} lots\n"
                    f"Price (signal): ₹{signal.price:.2f}\n"
                    f"Strike: {strike}\n"
                    f"Strength: {strength:.2f}\n"
                    f"Reason: {signal.reason}\n"
                    f"\n⚠️ **Failure**: API returned None\n"
                    f"Possible causes:\n"
                    f"- NFO segment not enabled\n"
                    f"- Invalid symbol\n"
                    f"- Exchange closed\n"
                    f"- Network issue"
                )
                logger.error(msg)
                log_order_result("N/A", symbol, qty, "FAILED", "API returned None")
                self.telegram.send_message(msg)
                
        except Exception as e:
            # Exception during order placement
            strength = abs(self.weightage_calc.calculate_weighted_strength())
            
            msg = (
                f"❌ **ORDER EXCEPTION**\n"
                f"Symbol: `{symbol}`\n"
                f"Type: {signal.type}\n"
                f"Action: **{action}** {qty} lots\n"
                f"Price (signal): ₹{signal.price:.2f}\n"
                f"Strike: {strike}\n"
                f"Strength: {strength:.2f}\n"
                f"Reason: {signal.reason}\n"
                f"\n⚠️ **Error**: {str(e)}\n"
            )
            logger.error(msg)
            log_order_result("N/A", symbol, qty, "EXCEPTION", str(e))
            self.telegram.send_message(msg)
