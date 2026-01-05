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
            min_hold_time=config.MIN_SIGNAL_HOLD_TIME,
            min_confirmation=config.MIN_SIGNAL_CONFIRMATION
        )
        
        # OMS Initialization
        self.position_manager = PositionManager()
        self.order_manager = OrderManager(self.shoonya, self.position_manager)
        self.auto_trading_enabled = False # Toggle via API
        
        self.paper_trading = PaperTradingEngine()
        
        self.token_map: Dict[str, str] = {} # Symbol -> Token
        self.reverse_token_map: Dict[str, str] = {} # Token -> Symbol
        
        from core.instruments import InstrumentManager
        self.instrument_mgr = InstrumentManager()
        self.tracked_atms: Dict[str, float] = {} # Symbol -> Current ATM Strike
        self.vwap_map = {} # Symbol -> {cum_vol, cum_pv, last_vol}
        self.tracked_stocks = set() # Set of underlying symbols to track for ATMs
        self.macro_data = {} # Symbol -> {trend, rsi, message}
        self.prev_close_map = {} # Symbol -> Prev Day Close
        self.price_history = []  # For momentum tracking
        
        # Order tracking
        self.current_order_id: str = None
        self.current_symbol: str = None
        self.current_entry_price = None  # Track entry price for P&L
        
        self.running = False
        self.offline = False  # Offline mode flag
        self.order_history = [] 
        try:
            from core.database import db
            self.db = db
            self.order_history = self.db.get_recent_orders(limit=50)
            
            # Load states from DB
            db_auto = self.db.get_state("auto_trading_enabled")
            if db_auto is not None:
                self.auto_trading_enabled = (db_auto == "True")
                
            db_paper = self.db.get_state("paper_trading_mode")
            if db_paper is not None:
                config.PAPER_TRADING_MODE = (db_paper == "True")
                
            logger.info(f"💾 TickEngine loaded history (Auto: {self.auto_trading_enabled}, Paper: {config.PAPER_TRADING_MODE}).")
        except Exception as e:
            logger.error(f"Failed to initialize TickEngine DB: {e}")
            self.db = None


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
        
        # 1. Resolve Benchmark (Prev Close)
        prev_close = self.prev_close_map.get(symbol, 0.0)
        if prev_close == 0:
            if 'pc' in tick:
                prev_close = float(tick.get('pc', 0))
            elif 'c' in tick and 'lp' in tick:
                # Deduce pc from change: pc = lp - change
                prev_close = float(tick['lp']) - float(tick['c'])
        
        # 2. Calculate Intraday Trend
        trend = "NEUTRAL"
        if current_vol > 0:
            # Stocks with volume use VWAP for trend
            vwap = self.vwap_map[symbol]['cum_pv'] / self.vwap_map[symbol]['cum_vol']
            if price > vwap: trend = "BULLISH"
            elif price < vwap: trend = "BEARISH"
        else:
            # Indices/Low-Volume use Price vs Benchmark
            if prev_close > 0:
                if price > prev_close: trend = "BULLISH"
                elif price < prev_close: trend = "BEARISH"
        
        # 3. Calculate VWAP for payload
        vwap = price
        if current_vol > 0 or self.vwap_map[symbol]['cum_vol'] > 0:
             vwap = self.vwap_map[symbol]['cum_pv'] / self.vwap_map[symbol]['cum_vol']

        # --- WEB DASHBOARD UPDATE ---
        try:
            # Import here to avoid circular dependencies if any
            from core.market_data import market_data
            
            # 4. Calculate Change and Percent Change
            change = 0.0
            percent_change = 0.0
            
            if prev_close > 0:
                change = price - prev_close
                percent_change = (change / prev_close) * 100
            elif 'c' in tick:
                # Absolute change from Shoonya
                change = float(tick['c'])
                percent_change = (change / price * 100) if price > 0 else 0.0
            
            # Sanity check for bad data
            if abs(percent_change) > 1000:
                percent_change = 0.0
                change = 0.0
                
            payload = {
                'symbol': symbol,
                'ltp': price,
                'volume': volume,
                'open': float(tick.get('o', 0)),
                'high': float(tick.get('h', 0)),
                'low': float(tick.get('l', 0)),
                'change': change,
                'percent_change': percent_change,
                'vwap': vwap,
                'trend': trend,
                'macro': self.macro_data.get(symbol, {}),
                'ai_signal': self._calculate_ai_signal(symbol, price, percent_change, vwap) if symbol == 'BANKNIFTY' else None,
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
            
            # Get Macro Trend for Bank Nifty
            macro = self.macro_data.get("BANKNIFTY", {}).get('trend', "NEUTRAL")

            # Run Strategy (Updated with multi-factor scoring)
            signal = self.strategy.on_tick(price, timestamp.timestamp(), vwap=vwap, macro_trend=macro)
            
            # Automation: Check for Trailing SL Breaches
            if self.auto_trading_enabled:
                # Check for TSL breaches in active positions
                for (sym, prd), pos in list(self.position_manager.positions.items()):
                    if pos["net_qty"] != 0 and self.position_manager.check_tsl_breach(sym, prd):
                        logger.warning(f"AUTO-TSL: Breach detected for {sym}. Triggering EXIT.")
                        tsl_signal = Signal("EXIT", sym, price, "Trailing Stop Loss Breach", timestamp.timestamp())
                        self.execute_signal(tsl_signal)
                
                # Check for Hard Stops (Daily Loss / Time)
                self._check_safety_limits()
            
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
            options = self.instrument_mgr.get_atm_option_tokens(symbol, strike, api=self.shoonya)
            
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
                     
                    # Identify Day Open (First candle of today)
                    day_open_price = 0.0
                    for candle in history:
                        try:
                            c_time = datetime.strptime(candle.get('time', ''), "%d-%m-%Y %H:%M:%S").replace(tzinfo=IST)
                            if c_time >= start_of_day:
                                day_open_price = float(candle.get('into', 0))
                                break
                        except: continue
                    
                    if day_open_price > 0:
                         self.weightage_calc.set_open_price(symbol, day_open_price)

                    
                    # --- POPULATE INITIAL UI DATA (Use LAST available candle) ---
                    if history:
                        last_candle = history[-1] # Get last available candle (even if yesterday)
                        close_price = float(last_candle.get('intc', 0))
                        
                        # Identify Previous Close (Last candle that is NOT from today)
                        prev_day_candle = None
                        for candle in reversed(history):
                             try:
                                 c_time = datetime.strptime(candle.get('time', ''), "%d-%m-%Y %H:%M:%S").replace(tzinfo=IST)
                                 if c_time < start_of_day:
                                     prev_day_candle = candle
                                     break
                             except: continue
                        
                        if prev_day_candle:
                            self.prev_close_map[symbol] = float(prev_day_candle.get('intc', 0))
                            logger.info(f"SET PREV CLOSE {symbol}: {self.prev_close_map[symbol]}")
                        
                        logger.info(f"DEBUG: Seeding {symbol} with close_price={close_price}")

                        # Fake payload to initialize UI
                        cur_prev_close = self.prev_close_map.get(symbol, close_price)
                        cur_change = close_price - cur_prev_close
                        cur_pct = (cur_change / cur_prev_close * 100) if cur_prev_close > 0 else 0.0

                        payload = {
                            'symbol': symbol,
                            'ltp': close_price,
                            'volume': int(last_candle.get('intv', 0)),
                            'open': float(last_candle.get('into', 0)),
                            'high': float(last_candle.get('inth', 0)),
                            'low': float(last_candle.get('intl', 0)),
                            'change': cur_change,
                            'percent_change': cur_pct,
                            'vwap': close_price,
                            'trend': 'NEUTRAL',
                            'macro': {},
                            'ai_signal': 'NEUTRAL', # Default for seed
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
                'ai_signal': 'OFFLINE (NEUTRAL)',
                'timestamp': datetime.now(IST).isoformat()
            }

    def _update_macro_data(self):
        """Fetch 30-day hourly history for macro trend analysis. Loops every hour."""
        while self.running:
            logger.info("🌊 Fetching Macro Data (30-Day Hourly Refresh)...")
            try:
                now = datetime.now(IST)
                start_time = now - timedelta(days=30)
                
                for symbol in self.tracked_stocks:
                    token = self.token_map.get(symbol)
                    if not token: continue
                    
                    # Fetch hourly (interval=60)
                    history = self.shoonya.get_history(exchange="NSE", token=token, 
                                                     start_time=start_time.timestamp(), 
                                                     interval="60")
                    
                    if history and isinstance(history, list):
                         df = pd.DataFrame(history)
                         df['close'] = pd.to_numeric(df['intc'])
                         
                         indicators = TechnicalIndicators.calculate_macro_trend(df)
                         self.macro_data[symbol] = indicators
                         logger.debug(f"MACRO {symbol} REFRESHED: {indicators}")
                         
                         time.sleep(0.5) # Throttling API calls
                    else:
                        logger.warning(f"No macro history for {symbol}")
                        
            except Exception as e:
                 logger.error(f"Macro Data Loop Error: {e}")
            
            # Wait 1 hour before next refresh
            for _ in range(3600):
                if not self.running: break
                time.sleep(1)

    def on_order_update(self, data):
        """Handle order updates from WebSocket"""
        logger.info(f"Order Update: {data}")
        
        # Log to orders file
        order_id = data.get('norenordno') or data.get('al_id') or 'N/A'
        symbol = data.get('tsym', 'N/A')
        status = data.get('status', 'N/A')
        product = data.get('prd', 'I') # MIS by default
        rejection_reason = data.get('rejreason', '')
        
        # Extract fill price and qty if available
        fill_price = float(data.get('avg_prc', 0)) if data.get('avg_prc') else 0.0
        fill_qty = int(data.get('fillqty', 0)) if data.get('fillqty') else 0
        side = data.get('trantype', 'BUY') # BUY/SELL
        
        additional_info = f"Rejection: {rejection_reason}" if rejection_reason and rejection_reason.strip() else ""
        log_order_update(order_id, symbol, status, additional_info)
        
        # Trigger Position Update on Full Fill
        if status == 'COMPLETE' and fill_qty > 0:
            if hasattr(self, 'position_manager'):
                self.position_manager.on_fill(symbol, fill_qty, fill_price, side, product)
        
        # Update existing order in history if found, else insert
        found = False
        for order in self.order_history:
            if order['id'] == order_id:
                order.update({
                    'status': status,
                    'reason': rejection_reason,
                    'price': fill_price if fill_price > 0 else order.get('price', 0),
                    'timestamp': datetime.now().isoformat()
                })
                if fill_qty > 0: order['qty'] = fill_qty
                
                # Update DB
                if self.db: self.db.save_order(order)
                found = True
                break
        
        if not found:
            # Buffer for sidebar
            order_data = {
                'id': order_id,
                'symbol': symbol,
                'status': status,
                'reason': rejection_reason,
                'price': fill_price,
                'qty': fill_qty,
                'timestamp': datetime.now().isoformat()
            }
            self.order_history.insert(0, order_data)
            if self.db: self.db.save_order(order_data)
            if len(self.order_history) > 50: self.order_history.pop()

        self.telegram.send_message(f"📊 Order Update: {status} ({symbol})")
        
    def place_manual_order(self, symbol: str, side: str, qty: int, price: float = 0.0, product_type: str = 'I'):
        """
        Handle Manual Order from UI
        product_type: 'I' (MIS), 'M' (NRML), 'C' (CNC)
        """
        logger.info(f"Manual Order Request: {side} {qty} {symbol} @ {price} ({product_type})")

        # --- OFFLINE/PAPER MODE ---
        if self.offline:
            return self._simulate_manual_order(symbol, side, qty, price, reason="OFFLINE")
            
        if config.PAPER_TRADING_MODE:
            return self._simulate_manual_order(symbol, side, qty, price, reason="PAPER_MODE")
        # ---------------------------
        
        # Delegate to OMS
        order_id = self.order_manager.place_order(symbol, side, qty, product_type=product_type, tag="MANUAL")
        
        if order_id:
            # ... (success logic)
            ltp = market_data.latest_prices.get(symbol, {}).get('ltp', 0.0)
            order_data = {
                'id': order_id,
                'symbol': symbol,
                'side': side,
                'qty': qty,
                'price': ltp,
                'status': 'PLACED',
                'timestamp': datetime.now().isoformat()
            }
            self.order_history.insert(0, order_data)
            if self.db:
                self.db.save_order(order_data)
            if len(self.order_history) > 50: self.order_history.pop()
            return {"status": "success", "order_id": order_id}
        else:
            logger.warning(f"OMS Order Failed for {symbol}. Falling back to Simulation.")
            return self._simulate_manual_order(symbol, side, qty, price, reason="FAILED")

    def cancel_order(self, order_id: str):
        """Cancel an order"""
        if self.offline or config.PAPER_TRADING_MODE:
            # Simple simulation: mark in history as cancelled
            for order in self.order_history:
                if order['id'] == order_id:
                    order['status'] = 'CANCELLED'
                    if self.db: self.db.save_order(order)
                    break
            return {"status": "success", "order_id": order_id}
            
        success = self.order_manager.cancel_order(order_id)
        return {"status": "success" if success else "error"}

    def place_gtt_order(self, symbol: str, side: str, qty: int, trigger_price: float, product_type: str = 'I'):
        """Place a GTT order"""
        if self.offline or config.PAPER_TRADING_MODE:
            # Simulate GTT placement
            gtt_id = f"GTT-SIM-{int(time.time())}"
            order_data = {
                'id': gtt_id,
                'symbol': symbol,
                'side': side,
                'qty': qty,
                'price': trigger_price,
                'status': 'GTT_PLACED',
                'timestamp': datetime.now().isoformat()
            }
            self.order_history.insert(0, order_data)
            if self.db: self.db.save_order(order_data)
            return {"status": "success", "gtt_id": gtt_id}

        gtt_id = self.order_manager.place_gtt_order(symbol, side, qty, trigger_price, product_type)
        if gtt_id:
            order_data = {
                'id': gtt_id,
                'symbol': symbol,
                'side': side,
                'qty': qty,
                'price': trigger_price,
                'status': 'GTT_PLACED',
                'timestamp': datetime.now().isoformat()
            }
            self.order_history.insert(0, order_data)
            if self.db: self.db.save_order(order_data)
            return {"status": "success", "gtt_id": gtt_id}
        return {"status": "error"}

    def _simulate_manual_order(self, symbol: str, side: str, qty: int, price: float = 0.0, reason: str = "SIM"):
        """Helper to simulate an offline order"""
        logger.warning(f"Simulation Mode ({reason}): {side} {qty} {symbol}")
        order_id = f"SIM-{int(time.time())}"
        
        # Simulate Fill
        ltp = market_data.latest_prices.get(symbol, {}).get('ltp', 0.0)
        fill_price = price if price > 0 else ltp
        if fill_price == 0: fill_price = 100.0 # Fallback default

        self.position_manager.on_fill(symbol, qty, fill_price, side)
        
        # Log to history
        order_data = {
            'id': order_id,
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'price': fill_price,
            'status': f'FILLED ({reason})',
            'timestamp': datetime.now().isoformat()
        }
        self.order_history.insert(0, order_data)
        if self.db:
            self.db.save_order(order_data)
            
        if len(self.order_history) > 50: self.order_history.pop()

        return {"status": "success", "order_id": order_id}
            
                

    def _calculate_ai_signal(self, symbol: str, price: float, pct_change: float, vwap: float) -> str:
        """
        Generate a consolidated AI Signal/Suggestion for the dashboard.
        Combines: Intraday Move, Macro (30D), Weighted Strength, and Momentum.
        """
        signal = "NEUTRAL"
        
        # 1. Get Weighted Strength (Constituents)
        strength = self.weightage_calc.calculate_weighted_strength()
        
        # 2. Get Macro Trend
        macro = self.macro_data.get(symbol, {}).get('trend', 'NEUTRAL')
        if isinstance(macro, list): macro = macro[0]
        
        # 3. Get Momentum (Relative to 2 mins ago)
        timestamp = datetime.now().timestamp()
        
        # We reuse the same history buffer if possible or maintain one here
        # For dashboard simplicity, we'll store on the class
        self.price_history.append((timestamp, price))
        while self.price_history and timestamp - self.price_history[0][0] > 600:
            self.price_history.pop(0)
            
        mom_score = 0.0
        if len(self.price_history) >= 2:
            lookback_time = timestamp - 120
            old_price = self.price_history[0][1]
            for t, p in reversed(self.price_history):
                if t <= lookback_time:
                    old_price = p
                    break
            change = price - old_price
            if change >= 60: mom_score = 1.5
            elif change >= 30: mom_score = 0.5
            elif change <= -60: mom_score = -1.5
            elif change <= -30: mom_score = -0.5
            
        score = 0
        
        # Factor A: Intraday Level (Relative to VWAP/Benchmark)
        if vwap > 0:
            if price > vwap: score += 1.0
            elif price < vwap: score -= 1.0
        
        # Factor B: Macro context
        if macro == "BULLISH": score += 1.0 
        elif macro == "BEARISH": score -= 1.0
        
        # Factor C: Constituent Strength
        if strength > 20: score += 1.5    
        elif strength > 10: score += 0.5  
        elif strength < -20: score -= 1.5
        elif strength < -10: score -= 0.5
        
        # Factor D: Momentum (The "Turnaround" factor)
        score += mom_score
        
        # Determine Final Signal
        if score >= 2.5: signal = "STRONG BUY 🚀"
        elif score >= 1.0: signal = "BUY 🟢"
        elif score <= -2.5: signal = "STRONG SELL 🩸"
        elif score <= -1.0: signal = "SELL 🔴"
        
        return signal

    def _check_safety_limits(self):
        """Monitor daily P&L and time to enforce hard stops."""
        if not self.auto_trading_enabled: return
        
        # 1. Daily Loss Limit
        total_pnl = self.position_manager.realized_pnl + self.position_manager.update_pnl(market_data.latest_prices)
        if total_pnl <= -config.MAX_DAILY_LOSS:
            logger.warning(f"🔥 HARD STOP: Daily Loss {total_pnl:.2f} reached limit {config.MAX_DAILY_LOSS}.")
            self.telegram.send_message(f"🚨 **HARD STOP ACTIVATED**\nDaily Loss: ₹{total_pnl:.2f}\nSHUTTING DOWN AUTO-TRADING.")
            self.execute_signal(Signal("EXIT", "BANKNIFTY", 0, "Daily Loss Limit", time.time()))
            self.auto_trading_enabled = False
            if self.db: self.db.save_state("auto_trading_enabled", "False")
            
        # 2. Time-Based Exit
        now_time = datetime.now(IST).strftime("%H:%M")
        if now_time >= config.AUTO_EXIT_TIME:
             logger.info(f"⏰ AUTO-EXIT TIME reached ({now_time}). Closing all.")
             self.telegram.send_message(f"⏰ **AUTO-EXIT TIME REACHED ({now_time})**\nSquaring off all positions.")
             self.execute_signal(Signal("EXIT", "BANKNIFTY", 0, "Time-Based Exit", time.time()))
             self.auto_trading_enabled = False
             if self.db: self.db.save_state("auto_trading_enabled", "False")

    def _get_option_symbol(self, option_type: str, strike: int) -> str:
        """Helper to construct Bank Nifty option symbol for current monthly expiry."""
        import calendar
        from datetime import datetime
        
        today = datetime.now()
        year, month = today.year, today.month
        
        # Find last Wednesday
        def get_last_wednesday(y, m):
            last_day = calendar.monthrange(y, m)[1]
            for d in range(last_day, 0, -1):
                if datetime(y, m, d).weekday() == 2: return datetime(y, m, d)
            return None

        expiry_date = get_last_wednesday(year, month)
        if today > expiry_date or (today.date() == expiry_date.date() and today.hour >= 15):
            year, month = (year, month + 1) if month < 12 else (year + 1, 1)
            expiry_date = get_last_wednesday(year, month)

        expiry_str = expiry_date.strftime("%d%b%y").upper()
        return f"BANKNIFTY{expiry_str}{option_type}{strike}"

    def _place_order_internal(self, symbol: str, action: str, signal_price: float, tag: str, signal_type: str):
        """Internal helper for consistent order placement and logging"""
        lot_size = self.instrument_mgr.get_lot_size("BANKNIFTY")
        qty = config.QUANTITY * lot_size
        
        logger.info(f"[{tag}] Attempting {action} {qty} {symbol}")
        log_order_attempt(action, symbol, qty, 0) # Strike placeholder

        if config.PAPER_TRADING_MODE or self.offline:
            # Paper Entry Logic
            self.paper_trading.enter_position(signal_type, signal_price, 0, qty, f"[{tag}] {signal_type}")
            msg = f"📝 PAPER {tag}: {action} {qty} {symbol} @ ₹{signal_price:.2f}"
            logger.info(msg)
            self.telegram.send_message(msg)
            return

        try:
            order_id = self.shoonya.place_order(
                buy_or_sell=action, product_type="M", exchange="NFO",
                tradingsymbol=symbol, quantity=qty, discloseqty=0,
                price_type="MKT", price=0, trigger_price=None,
                retention="DAY", remarks=f"Auto-{tag}-{signal_type}"
            )
            if order_id:
                msg = f"✅ [{tag}] ORDER PLACED: {symbol} (ID: {order_id})"
                logger.info(msg)
                self.telegram.send_message(msg)
            else:
                logger.error(f"❌ [{tag}] ORDER FAILED for {symbol}")
        except Exception as e:
            logger.error(f"❌ [{tag}] EXCEPTION for {symbol}: {e}")

    def _handle_exit_signal(self, signal):
        """Close all active Bank Nifty option positions"""
        logger.info("Handling Global EXIT for Bank Nifty positions...")
        
        active_found = False
        # Iterate over all positions in position_manager
        # (Using list to avoid 'dictionary changed size' during iteration)
        for (symbol, product), pos in list(self.position_manager.positions.items()):
            if "BANKNIFTY" in symbol and pos["net_qty"] != 0:
                active_found = True
                action = "S" if pos["net_qty"] > 0 else "B"
                qty = abs(pos["net_qty"])
                
                logger.info(f"Closing position: {symbol} ({qty} qty)")
                
                if config.PAPER_TRADING_MODE or self.offline:
                    pnl = self.paper_trading.exit_position(signal.price, signal.reason)
                    msg = f"📝 PAPER EXIT: {symbol} P&L: ₹{pnl:.2f}"
                else:
                    order_id = self.shoonya.place_order(
                        buy_or_sell=action, product_type=product, exchange="NFO",
                        tradingsymbol=symbol, quantity=qty, discloseqty=0,
                        price_type="MKT", price=0, trigger_price=None,
                        retention="DAY", remarks=f"Auto-EXIT-{signal.reason}"
                    )
                    msg = f"⏹️ EXIT ORDER PLACED: {symbol} (ID: {order_id})"
                
                logger.info(msg)
                self.telegram.send_message(msg)

        if not active_found:
            logger.info("No active Bank Nifty positions to exit.")

    def execute_signal(self, signal):
        """Execute the signal with support for Hedged ATM and Straddles."""
        logger.info(f"🚀 EXECUTING {signal.type} @ {signal.price}")
        
        if signal.type == "EXIT":
            self._handle_exit_signal(signal)
            return

        orders = []
        base_atm = round(signal.price / 100) * 100
        
        if signal.type == "BUY_STRADDLE":
            orders.append({'type': 'C', 'strike': base_atm, 'tag': 'MAIN'})
            orders.append({'type': 'P', 'strike': base_atm, 'tag': 'MAIN'})
        
        elif signal.type in ["BUY_CE", "BUY_PE"]:
            strength = abs(self.weightage_calc.calculate_weighted_strength())
            offset = 200 if strength > 8.0 else (100 if strength > 6.5 else 0)
            
            if "CE" in signal.type:
                orders.append({'type': 'C', 'strike': base_atm + offset, 'tag': 'MAIN'})
                if config.HEDGED_ENTRIES:
                    orders.append({'type': 'P', 'strike': base_atm - config.HEDGE_OTM_STEP, 'tag': 'WING'})
            else:
                orders.append({'type': 'P', 'strike': base_atm - offset, 'tag': 'MAIN'})
                if config.HEDGED_ENTRIES:
                    orders.append({'type': 'C', 'strike': base_atm + config.HEDGE_OTM_STEP, 'tag': 'WING'})

        for order in orders:
            symbol = self._get_option_symbol(order['type'], order['strike'])
            self._place_order_internal(symbol, "B", signal.price, order['tag'], signal.type)
