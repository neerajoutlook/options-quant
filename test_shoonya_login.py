#!/usr/bin/env python3
"""
Minimal Shoonya Login Test
Tests if Shoonya API is responding correctly
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import os
import pyotp
from NorenRestApiPy.NorenApi import NorenApi
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Get credentials
user = os.getenv("SHOONYA_USER")
pwd = os.getenv("SHOONYA_PWD")
api_key = os.getenv("SHOONYA_API_KEY")
totp_seed = os.getenv("SHOONYA_TOTP")
vendor = os.getenv("SHOONYA_VENDOR")

# Generate OTP
def totp_from_seed(seed: str) -> str:
    """Generate TOTP from seed"""
    return pyotp.TOTP(seed).now()

otp = totp_from_seed(totp_seed)

print(f"Testing Shoonya Login")
print(f"User: {user}")
print(f"OTP: {otp}")
print(f"Vendor: {vendor}")
print("-" * 60)

# Create API instance
api = NorenApi(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')

# Try login with detailed error handling
try:
    print(f"Attempting login...")
    ret = api.login(
        userid=user,
        password=pwd,
        twoFA=otp,
        vendor_code=vendor,
        api_secret=api_key,
        imei="abc1234"
    )
    
    print(f"Response type: {type(ret)}")
    print(f"Response: {ret}")
    
    if ret and isinstance(ret, dict) and ret.get('stat') == 'Ok':
        print("\n✅ LOGIN SUCCESSFUL!")
    else:
        print(f"\n❌ LOGIN FAILED: {ret}")
        
except Exception as e:
    print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
