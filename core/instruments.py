"""
Instrument Manager
Handles lookup of Option tokens, ATM calculations, and Symbol management.
"""
import logging
import math
from typing import Dict, Optional, List
import requests
import pandas as pd
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Strike Step Sizes for Bank Nifty Constituents (Approximate/Standard)
# TODO: dynamically fetch if possible, but hardcoded maps are faster/safer for now
STRIKE_STEPS = {
    "HDFCBANK": 10,
    "ICICIBANK": 10,
    "SBIN": 5,
    "KOTAKBANK": 10,
    "AXISBANK": 10,
    "INDUSINDBK": 10,
    "BANDHANBNK": 5, # or 2.5 under 200? usually 5
    "FEDERALBNK": 5,
    "IDFCFIRSTB": 1, # or 0.5?
    "PNB": 1, # or 0.5
    "AUBANK": 10,
    "BANKBARODA": 1, # check
    "BANKNIFTY": 100,
    "NIFTY": 50
}

class InstrumentManager:
    def __init__(self):
        self.master_path = "data/NFO_instruments.txt"
        self.option_map = {} # Symbol -> { Expiry -> { Strike -> { 'CE': token, 'PE': token } } }
        self.expiry_map = {} # Symbol -> Sorted List of Expiry Dates
        self.lot_size_map = {} # Symbol -> Lot Size (int)
        
        self.load_master_contract()
        
    def load_master_contract(self):
        """Load NFO master contract file"""
        if not os.path.exists(self.master_path):
            logger.error(f"Master file not found at {self.master_path}")
            return

        logger.info(f"Loading master contract from {self.master_path}...")
        try:
            # Simple CSV parsing (faster than pandas for this specific structure if we just iterate)
            # Format: NFO,Token,Lot,Symbol,TSym,Expiry(DD-MMM-YYYY),Inst,OptType,Strike,Tick
            
            with open(self.master_path, 'r') as f:
                for line in f:
                    parts = line.split(',')
                    if len(parts) < 9: continue
                    
                    # focus on OPTSTK (Stock Options) and OPTIDX (Index Options)
                    inst = parts[6]
                    if inst not in ['OPTSTK', 'OPTIDX']:
                        continue
                        
                    token = parts[1]
                    lot_size = int(parts[2])
                    symbol = parts[3]
                    expiry_str = parts[5] # 24-FEB-2026
                    opt_type = parts[7]   # CE/PE
                    strike = float(parts[8])
                    
                    # Store Lot Size (Updating it repeatedly is fine, usually constant for a symbol)
                    self.lot_size_map[symbol] = lot_size
                    
                    # Convert Expiry to date object for sorting
                    try:
                        expiry_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
                    except:
                        continue
                        
                    # Build Tree
                    if symbol not in self.option_map:
                        self.option_map[symbol] = {}
                        self.expiry_map[symbol] = set()
                        
                    if expiry_date not in self.option_map[symbol]:
                        self.option_map[symbol][expiry_date] = {}
                        self.expiry_map[symbol].add(expiry_date)
                        
                    if strike not in self.option_map[symbol][expiry_date]:
                        self.option_map[symbol][expiry_date][strike] = {}
                        
                    self.option_map[symbol][expiry_date][strike][opt_type] = {
                        'token': token,
                        'tsym': parts[4]
                    }
            
            # Sort expiries
            for sym in self.expiry_map:
                self.expiry_map[sym] = sorted(list(self.expiry_map[sym]))
                
            logger.info(f"Loaded options for {len(self.option_map)} symbols. Lot sizes mapped.")
            
        except Exception as e:
            logger.error(f"Failed to load master contract: {e}")

    def get_lot_size(self, symbol: str) -> int:
        """Get Lot Size for a symbol (defaults to 1 if not found)"""
        return self.lot_size_map.get(symbol, 1)

    def get_step_size(self, symbol: str) -> float:
        if symbol in STRIKE_STEPS:
            return STRIKE_STEPS[symbol]
        return 5.0 # Default

    def calculate_atm_strike(self, symbol: str, ltp: float) -> float:
        step = self.get_step_size(symbol)
        strike = round(ltp / step) * step
        if step < 1: return round(strike, 2)
        return int(strike)

    def get_atm_option_tokens(self, symbol: str, strike: float) -> Optional[Dict]:
        """Get CE and PE tokens for the nearest expiry at this strike"""
        if symbol not in self.option_map:
            logger.warning(f"Symbol {symbol} not in option map")
            return None
            
        # Find nearest expiry (strictly future or today)
        today = datetime.now().date()
        valid_expiries = [d for d in self.expiry_map[symbol] if d >= today]
        
        if not valid_expiries:
            logger.warning(f"No future expiry found for {symbol}")
            return None
            
        nearest_expiry = valid_expiries[0]
        
        # Look for exact strike match (allow small float tolerance)
        # Note: formatting keys as floats, but tolerance is safe
        
        # Check direct lookup first
        options = self.option_map[symbol][nearest_expiry].get(strike)
        
        # If not found, try fuzzy text (sometimes strike 600.0 is key 600)
        # But we parsed as float, so it should match if strike is passed as float
        
        if options:
            return options
        else:
            logger.warning(f"Strike {strike} not found for {symbol} in expiry {nearest_expiry}")
            return None

