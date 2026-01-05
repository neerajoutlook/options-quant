"""
Utility script to fetch live prices from Shoonya API and cache them for simulation.
Run this before starting the simulator to ensure realistic prices.

Usage:
    python scripts/fetch_live_prices.py
"""
import sys
import os
import json
from datetime import date

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.shoonya_client import ShoonyaSession
from core.config import SIMULATION_MODE

def fetch_and_cache_live_prices():
    """Fetch live prices from Shoonya and cache them"""
    
    # Token map (same as in simulator)
    token_map = {
        'BANKNIFTY': '99926000',
        'HDFCBANK': '1333',
        'ICICIBANK': '4963',
        'SBIN': '3045',
        'AXISBANK': '5900',
        'KOTAKBANK': '1922',
        'INDUSINDBK': '5258',
        'BANDHANBNK': '579',
        'FEDERALBNK': '1023',
        'IDFCFIRSTB': '11184',
        'PNB': '10666',
        'AUBANK': '21238',
        'NIFTY': '99926009'
    }
    
    cache_file = os.path.join(os.path.dirname(__file__), "../data/sim_base_prices.json")
    base_prices = {}
    
    # Connect to Shoonya
    print("=" * 80)
    print("FETCHING LIVE PRICES FROM SHOONYA API")
    print("=" * 80)
    print()
    
    try:
        api = ShoonyaSession()
        print("🔐 Logging in to Shoonya...")
        api.login()
        print("✅ Login successful\n")
        
        # Fetch quotes for each symbol
        for symbol, token in token_map.items():
            # Skip option symbols
            if any(char.isdigit() for char in symbol[:-1]) or 'CE' in symbol or 'PE' in symbol:
                continue
            
            try:
                # Determine exchange
                if symbol in ['BANKNIFTY', 'NIFTY', 'FINNIFTY']:
                    exchange = "NFO"
                else:
                    exchange = "NSE"
                
                # Fetch quote
                quote = api.get_quotes(exchange, token)
                
                if quote and 'lp' in quote:
                    live_price = float(quote['lp'])
                    base_prices[symbol] = round(live_price, 2)
                    print(f"✅ {symbol:15s} ₹{live_price:10.2f} ({exchange})")
                else:
                    print(f"⚠️  {symbol:15s} No quote available")
            except Exception as e:
                print(f"❌ {symbol:15s} Error: {e}")
        
        print()
        print(f"Fetched {len(base_prices)}/{len(token_map)} live prices")
        
        # Save to cache
        if base_prices:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump({
                    'date': date.today().isoformat(),
                    'prices': base_prices
                }, f, indent=2)
            print(f"\n💾 Cached prices to: {cache_file}")
            print("\n✅ Ready for simulation with realistic prices!")
        else:
            print("\n⚠️  No prices fetched - using fallbacks")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nℹ️  TIP: Make sure SIMULATION_MODE is FALSE to login to Shoonya")
        return False

if __name__ == "__main__":
    success = fetch_and_cache_live_prices()
    sys.exit(0 if success else 1)
