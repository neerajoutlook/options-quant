"""
Order logger - separate logging for all order events
"""
import logging
from pathlib import Path
from datetime import datetime

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Create separate order logger
order_logger = logging.getLogger("order_log")
order_logger.setLevel(logging.INFO)

# Create handler for order-specific log file
order_handler = logging.FileHandler("logs/orders.log")
order_handler.setLevel(logging.INFO)

# Format: timestamp | order_type | symbol | quantity | status | details
order_formatter = logging.Formatter('%(asctime)s | %(message)s')
order_handler.setFormatter(order_formatter)

order_logger.addHandler(order_handler)

# Don't propagate to root logger
order_logger.propagate = False

def log_signal(signal_type, symbol, price, strength, reason):
    """Log trading signal generation"""
    order_logger.info(f"SIGNAL | {signal_type} | {symbol} | Price: {price:.2f} | Strength: {strength:.2f} | {reason}")

def log_order_attempt(action, symbol, quantity, strike=None):
    """Log order placement attempt"""
    strike_info = f" | Strike: {strike}" if strike else ""
    order_logger.info(f"ORDER_ATTEMPT | {action} | {symbol} | Qty: {quantity}{strike_info}")

def log_order_result(order_id, symbol, quantity, status, reason=""):
    """Log order result (success/failure)"""
    reason_info = f" | Reason: {reason}" if reason else ""
    order_logger.info(f"ORDER_RESULT | ID: {order_id} | {symbol} | Qty: {quantity} | {status}{reason_info}")

def log_order_update(order_id, symbol, status, additional_info=""):
    """Log order status updates from WebSocket"""
    info = f" | {additional_info}" if additional_info else ""
    order_logger.info(f"ORDER_UPDATE | ID: {order_id} | {symbol} | {status}{info}")

def log_position_change(action, symbol, quantity):
    """Log position entries/exits"""
    order_logger.info(f"POSITION | {action} | {symbol} | Qty: {quantity}")
