import os
import time
import threading
import hmac
import base64
import struct
import hashlib
import logging
from typing import Callable, List, Optional, Dict

from NorenRestApiPy.NorenApi import NorenApi
from core.config import (SHOONYA_USER, SHOONYA_PWD, SHOONYA_API_KEY, 
                          SHOONYA_TOTP, SHOONYA_VENDOR, SHOONYA_IMEI)

logger = logging.getLogger(__name__)

def totp_from_seed(seed: str) -> str:
    """Compute 6-digit TOTP code from a base32 seed."""
    if not seed:
        return ""
    s = seed.strip().replace(" ", "").upper()
    pad = "=" * ((8 - len(s) % 8) % 8)
    key = base64.b32decode(s + pad, casefold=True)
    counter = int(time.time() // 30)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = (int.from_bytes(h[o:o + 4], "big") & 0x7FFFFFFF) % (10 ** 6)
    return str(code).zfill(6)

class ShoonyaSession:
    """
    Wrapper around NorenApi to manage login and WebSocket session.
    """

    def __init__(self,
                 host: str = 'https://api.shoonya.com/NorenWClientTP/',
                 websocket: str = 'wss://api.shoonya.com/NorenWSTP/'):
        self.api = NorenApi(host=host, websocket=websocket)
        self._ws_started = False
        self._ws_lock = threading.Lock()

    def login(self) -> dict:
        """Login to Shoonya using credentials from config."""
        # Strip whitespace from credentials to avoid hashing errors
        user = SHOONYA_USER.strip() if SHOONYA_USER else None
        pwd = SHOONYA_PWD.strip() if SHOONYA_PWD else None
        api_key = SHOONYA_API_KEY.strip() if SHOONYA_API_KEY else None
        vendor = SHOONYA_VENDOR.strip() if SHOONYA_VENDOR else user
        
        if not all([user, pwd, api_key]):
            logger.error(f"Missing credentials: USER={bool(user)}, PWD={bool(pwd)}, API_KEY={bool(api_key)}")
            raise RuntimeError("Missing Shoonya credentials in config/environment")

        otp = totp_from_seed(SHOONYA_TOTP)
        logger.info(f"Attempting login for user: {user} with OTP: {otp}")
        
        try:
            logger.info(f"Trying login with vendor_code: '{vendor}'")
            ret = self.api.login(
                userid=user,
                password=pwd,
                twoFA=otp,
                vendor_code=vendor,
                api_secret=api_key,
                imei=SHOONYA_IMEI
            )
            
            if not ret or ret.get('stat') != 'Ok':
                logger.error(f"Shoonya login failed: {ret}")
                raise RuntimeError(f"Shoonya login failed: {ret}")
                
            logger.info(f"✅ Shoonya login successful for {user}")
            return ret
            
        except Exception as e:
            logger.error(f"Shoonya Login Exception: {e}")
            raise RuntimeError(f"Shoonya login failed: {e}")

    def start_websocket(self,
                        on_ticks: Callable[[dict], None],
                        on_orders: Optional[Callable[[dict], None]] = None,
                        on_connect: Optional[Callable[[], None]] = None) -> None:
        """Start the WebSocket connection."""
        with self._ws_lock:
            if self._ws_started:
                return
            self._ws_started = True

        def _open():
            if on_connect:
                on_connect()
            else:
                logger.info("✅ Shoonya WebSocket connected")

        self.api.start_websocket(order_update_callback=on_orders,
                                 subscribe_callback=on_ticks,
                                 socket_open_callback=_open)

    def subscribe(self, instruments: List[str]):
        """Subscribe to a list of instruments (e.g. ['NSE|22', 'NFO|12345'])."""
        self.api.subscribe(instruments)

    def unsubscribe(self, instruments: List[str]):
        """Unsubscribe from a list of instruments."""
        self.api.unsubscribe(instruments)
        
    def close_websocket(self):
        """Close the WebSocket connection."""
        with self._ws_lock:
            if not self._ws_started:
                return
            self._ws_started = False
            
        try:
            # Attempt to close if method exists
            if hasattr(self.api, 'close_websocket'):
                self.api.close_websocket()
            elif hasattr(self.api, 'stop_websocket'):
                self.api.stop_websocket()
            else:
                logger.warning("⚠️ NorenApi does not have close_websocket/stop_websocket method")
        except Exception as e:
            logger.error(f"❌ Error closing WebSocket: {e}")
        
    def get_security_info(self, exchange: str, token: str):
        """Get security info."""
        return self.api.get_security_info(exchange=exchange, token=token)
        
    def search_scrip(self, exchange: str, searchstr: str):
        """Search for scrips."""
        logger.info(f"Searching scrip: exchange={exchange}, searchstr={searchstr}")
        ret = self.api.searchscrip(exchange=exchange, searchtext=searchstr)
        logger.info(f"Search result for {searchstr}: {ret}")
        return ret

    def get_history(self, exchange: str, token: str, start_time: float, end_time: float = None, interval: int = 1):
        """
        Get historical data.
        start_time, end_time: Epoch timestamp (seconds) or datetime objects
        interval: 1 (1 minute), 3, 5, etc.
        """
        if end_time is None:
            end_time = time.time()
            
        ret = self.api.get_time_price_series(exchange=exchange, token=token, starttime=start_time, endtime=end_time, interval=interval)
        return ret

    def place_order(self, 
                   buy_or_sell: str, 
                   product_type: str,
                   exchange: str, 
                   tradingsymbol: str, 
                   quantity: int, 
                   discloseqty: int, 
                   price_type: str, 
                   price: float = 0.0, 
                   trigger_price: float = None,
                   retention: str = 'DAY', 
                   remarks: str = None) -> Optional[str]:
        """
        Place an order.
        buy_or_sell: 'B' or 'S'
        product_type: 'C' (CNC), 'M' (MIS), 'I' (NRML)
        exchange: 'NSE', 'NFO', 'BSE'
        price_type: 'LMT', 'MKT', 'SL-LMT', 'SL-MKT'
        """
        try:
            logger.info(f"Placing Order: {buy_or_sell} {quantity} {tradingsymbol} @ {price} ({product_type})")
            logger.debug(f"Order params: exchange={exchange}, product={product_type}, price_type={price_type}")
            
            ret = self.api.place_order(buy_or_sell=buy_or_sell,
                                     product_type=product_type,
                                     exchange=exchange,
                                     tradingsymbol=tradingsymbol,
                                     quantity=quantity,
                                     discloseqty=discloseqty,
                                     price_type=price_type,
                                     price=price,
                                     trigger_price=trigger_price,
                                     retention=retention,
                                     remarks=remarks)
            
            logger.info(f"API Response: {ret}")  # Log full response
            
            if ret and ret.get('stat') == 'Ok':
                order_id = ret.get('norenordno')
                logger.info(f"✅ Order placed successfully. Order ID: {order_id}")
                return order_id
            else:
                error_msg = ret.get('emsg', 'Unknown error') if ret else 'API returned None'
                logger.error(f"❌ Order placement failed: {error_msg}")
                logger.error(f"❌ Full response: {ret}")
                return None
        except Exception as e:
            logger.error(f"❌ Order placement exception: {e}")
            logger.exception("Full traceback:")
            return None

    def get_historical_data(self, exchange: str, token: str, start_time: float = None, end_time: float = None, interval: str = '1') -> Optional[List[Dict]]:
        """
        Get historical time-price series data.
        interval: '1' (1 minute), '3', '5', '10', '15', '30', '60', 'D' (Daily)
        start_time: epoch timestamp (optional, defaults to beginning of today)
        end_time: epoch timestamp (optional, defaults to now)
        """
        try:
            # Default to last 5 days if not specified
            if not start_time:
                start_time = time.time() - (5 * 24 * 60 * 60)
            if not end_time:
                end_time = time.time()
                
            # logger.info(f"Fetching history for {exchange}|{token} interval={interval}")
            
            ret = self.api.get_time_price_series(exchange=exchange, token=token, starttime=start_time, endtime=end_time, interval=interval)
            
            if ret:
                # NorenApi usually returns a list of dicts or None
                # Format: [{'time': '...', 'into': '...', 'inth': '...', 'intl': '...', 'intc': '...', 'intv': '...'}]
                return ret
            else:
                # logger.warning(f"No historical data found for {exchange}|{token}")
                return None
        except Exception as e:
            logger.error(f"Error fetching history for {exchange}|{token}: {e}")
            return None
