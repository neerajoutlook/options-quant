#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/neerajsharma/personal/python-projects/options-quant')

from core.shoonya_client import ShoonyaSession
import logging

logging.basicConfig(level=logging.INFO)

session = ShoonyaSession()
session.login()

# Search for NIFTY options on NFO
print("\n🔍 Searching for NIFTY options on NFO:")
ret = session.search_scrip(exchange="NFO", searchstr="NIFTY")
if ret and ret.get('values'):
    print(f"   Found {len(ret['values'])} results")
    # Show some weekly options
    for item in ret['values'][:10]:
        tsym = item.get('tsym', '')
        if 'NIFTY' in tsym and ('PE' in tsym or 'CE' in tsym):
            print(f"   ✅ {tsym} - Token: {item.get('token')}")
else:
    print(f"   ❌ No results")

# Try searching for specific BANKNIFTY
print("\n🔍 Searching for BANKNIFTY options on NFO:")
ret = session.search_scrip(exchange="NFO", searchstr="BANKNIFTY")
if ret and ret.get('values'):
    print(f"   Found {len(ret['values'])} results")
    for item in ret['values'][:5]:
        tsym = item.get('tsym', '')
        if 'PE' in tsym or 'CE' in tsym:
            print(f"   ✅ {tsym} - Token: {item.get('token')}")
            
print("\n💡 Note: Sensex options may not be available on Shoonya.")
print("   Consider switching to NIFTY or BANKNIFTY for options trading.")
