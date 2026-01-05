#!/usr/bin/env python3
"""
Test script to find the correct Sensex options symbol format
"""
import sys
sys.path.insert(0, '/Users/neerajsharma/personal/python-projects/options-quant')

from core.shoonya_client import ShoonyaSession
import logging

logging.basicConfig(level=logging.INFO)

def test_symbol_search():
    session = ShoonyaSession()
    session.login()
    
    # Search for Sensex options
    print("\n1. Searching for SENSEX options on BFO:")
    ret = session.search_scrip(exchange="BFO", searchstr="SENSEX")
    if ret and ret.get('values'):
        print(f"   Found {len(ret['values'])} results:")
        for item in ret['values'][:5]:  # Show first 5
            print(f"   - Token: {item.get('token')}, Symbol: {item.get('tsym')}, Name: {item.get('cname')}")
    else:
        print(f"   No results or error: {ret}")
    
    # Try NFO
    print("\n2. Searching for SENSEX options on NFO:")
    ret = session.search_scrip(exchange="NFO", searchstr="SENSEX")
    if ret and ret.get('values'):
        print(f"   Found {len(ret['values'])} results:")
        for item in ret['values'][:5]:
            print(f"   - Token: {item.get('token')}, Symbol: {item.get('tsym')}, Name: {item.get('cname')}")
    else:
        print(f"   No results or error: {ret}")
    
    # Try BSE
    print("\n3. Searching for SENSEX options on BSE:")
    ret = session.search_scrip(exchange="BSE", searchstr="SENSEX")
    if ret and ret.get('values'):
        print(f"   Found {len(ret['values'])} results:")
        for item in ret['values'][:10]:
            if 'PE' in item.get('tsym', '') or 'CE' in item.get('tsym', ''):
                print(f"   - Token: {item.get('token')}, Symbol: {item.get('tsym')}, Name: {item.get('cname')}")
    else:
        print(f"   No results or error: {ret}")

if __name__ == "__main__":
    test_symbol_search()
