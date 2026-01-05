import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# Add trading-software to path
sys.path.append("/Users/neerajsharma/personal/python-projects/trading-software")

from core.shoonya_client import ShoonyaSession
from config.config import SHOONYA_USER, SHOONYA_PWD, SHOONYA_API_KEY, SHOONYA_VENDOR

print(f"Testing login with trading-software code for user: {SHOONYA_USER}")
print(f"Vendor: {SHOONYA_VENDOR}")
print(f"API Key Length: {len(SHOONYA_API_KEY) if SHOONYA_API_KEY else 0}")

session = ShoonyaSession()
try:
    ret = session.login()
    print(f"Login Result: {ret}")
except Exception as e:
    print(f"Login Failed: {e}")
