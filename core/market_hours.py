"""
Market hours detection for Indian stock market (NSE/BSE)
"""
from datetime import datetime, time
import pytz

IST = pytz.timezone('Asia/Kolkata')

def is_market_open() -> bool:
    """
    Check if Indian stock market is currently open.
    Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST
    """
    now = datetime.now(IST)
    
    # Check if weekend
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Check if within market hours
    market_start = time(9, 15)  # 9:15 AM
    market_end = time(15, 30)   # 3:30 PM
    
    current_time = now.time()
    return market_start <= current_time <= market_end

from core import config

def get_market_status() -> dict:
    """
    Get detailed market status information.
    Returns dict with: is_open, reason, next_open_time, mode, simulation_speed
    """
    now = datetime.now(IST)
    is_open = is_market_open()
    
    if is_open:
        return {
            "is_open": True,
            "reason": "Market is open",
            "mode": "LIVE",
            "simulation_speed": config.SIMULATION_SPEED,
            "simulation_mode": config.SIMULATION_MODE
        }
    
    # Determine reason for closure
    if now.weekday() >= 5:
        reason = f"Weekend ({now.strftime('%A')})"
    else:
        current_time = now.time()
        if current_time < time(9, 15):
            reason = "Before market hours (opens 9:15 AM IST)"
        else:
            reason = "After market hours (closed at 3:30 PM IST)"
    
    return {
        "is_open": False,
        "reason": reason,
        "mode": "SIMULATION",
        "simulation_speed": config.SIMULATION_SPEED,
        "simulation_mode": config.SIMULATION_MODE
    }

def should_auto_enable_simulation() -> bool:
    """
    Returns True if simulation mode should be auto-enabled.
    This happens when market is closed.
    """
    return not is_market_open()
