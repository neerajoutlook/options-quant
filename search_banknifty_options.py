#!/usr/bin/env python3
"""Search for valid Bank Nifty option symbols"""
import sys
sys.path.insert(0, '/Users/neerajsharma/personal/python-projects/options-quant')

from core.shoonya_client import ShoonyaSession
import logging

logging.basicConfig(level=logging.INFO)

session = ShoonyaSession()
session.login()

# Search for Bank Nifty options
print("\n🔍 Searching for Bank Nifty options on NFO:")
ret = session.search_scrip(exchange="NFO", searchstr="BANKNIFTY")

if ret and ret.get('values'):
    print(f"Found {len(ret['values'])} results:\n")
    for item in ret['values'][:15]:  # Show first 15
        tsym = item.get('tsym', '')
        token = item.get('token', '')
        instname = item.get('instname', '')
        print(f"{tsym:30s} Token: {token:10s} Type: {instname}")
else:
    print("❌ No results found")
    print(f"Response: {ret}")
