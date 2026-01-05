"""
Test to verify that all simulated stock prices result in valid option strikes.
This ensures we can find options for all stocks during simulation.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.instruments import InstrumentManager, STRIKE_STEPS
import yfinance as yf

def test_all_stocks_have_valid_strikes():
    """Fetch live prices and verify we can find ATM strikes for all stocks"""
    
    # Symbols to test (Bank Nifty constituents)
    test_symbols = {
        'BANKNIFTY': '^NSEBANK',
        'HDFCBANK': 'HDFCBANK.NS',
        'ICICIBANK': 'ICICIBANK.NS',
        'SBIN': 'SBIN.NS',
        'AXISBANK': 'AXISBANK.NS',
        'KOTAKBANK': 'KOTAKBANK.NS',
        'INDUSINDBK': 'INDUSINDBK.NS',
        'BANDHANBNK': 'BANDHANBNK.NS',
        'FEDERALBNK': 'FEDERALBNK.NS',
        'IDFCFIRSTB': 'IDFCFIRSTB.NS',
        'PNB': 'PNB.NS',
        'AUBANK': 'AUBANK.NS'
    }
    
    # Load instrument manager
    inst_mgr = InstrumentManager()
    
    results = []
    failed = []
    
    print("\n" + "="*80)
    print("TESTING STRIKE AVAILABILITY FOR SIMULATED PRICES")
    print("="*80 + "\n")
    
    for symbol, yf_symbol in test_symbols.items():
        try:
            # Fetch live price
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period='1d')
            
            if hist.empty:
                print(f"⚠️  {symbol:15s} - Could not fetch price")
                continue
            
            live_price = hist['Close'].iloc[-1]
            
            # Calculate ATM strike
            atm_strike = inst_mgr.calculate_atm_strike(symbol, live_price)
            
            # Try to find options for this strike
            options = inst_mgr.get_atm_option_tokens(symbol, atm_strike)
            
            if options:
                print(f"✅ {symbol:15s} LTP: ₹{live_price:8.2f} → Strike: {atm_strike:6.0f} | CE: {options['CE']['tsym']}")
                results.append({
                    'symbol': symbol,
                    'ltp': live_price,
                    'strike': atm_strike,
                    'found': True
                })
            else:
                print(f"❌ {symbol:15s} LTP: ₹{live_price:8.2f} → Strike: {atm_strike:6.0f} | NOT FOUND")
                failed.append({
                    'symbol': symbol,
                    'ltp': live_price,
                    'strike': atm_strike
                })
                results.append({
                    'symbol': symbol,
                    'ltp': live_price,
                    'strike': atm_strike,
                    'found': False
                })
                
        except Exception as e:
            print(f"❌ {symbol:15s} - Error: {e}")
            failed.append({'symbol': symbol, 'error': str(e)})
    
    print("\n" + "="*80)
    print(f"RESULTS: {len(results) - len(failed)}/{len(results)} strikes found")
    print("="*80)
    
    if failed:
        print("\n⚠️  FAILED SYMBOLS:")
        for item in failed:
            if 'error' in item:
                print(f"  - {item['symbol']}: {item['error']}")
            else:
                print(f"  - {item['symbol']}: Strike {item['strike']} not in master file")
        print("\n💡 These symbols need strike step size or master file updates")
    else:
        print("\n🎉 All strikes found successfully!")
    
    return len(failed) == 0

if __name__ == "__main__":
    success = test_all_stocks_have_valid_strikes()
    sys.exit(0 if success else 1)
