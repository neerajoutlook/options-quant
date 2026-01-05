import os
import sys
from dotenv import load_dotenv
from NorenRestApiPy.NorenApi import NorenApi
import logging
from datetime import datetime

# Redefine TOTP internally to ensure parity
import hmac
import base64
import struct
import hashlib
import time

def totp_from_seed(seed: str) -> str:
    if not seed: return ""
    s = seed.strip().replace(" ", "").upper()
    pad = "=" * ((8 - len(s) % 8) % 8)
    key = base64.b32decode(s + pad, casefold=True)
    counter = int(time.time() // 30)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = (int.from_bytes(h[o:o + 4], "big") & 0x7FFFFFFF) % (10 ** 6)
    return str(code).zfill(6)

# Load env
load_dotenv(override=True)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("diag")

user = os.getenv("SHOONYA_USER")
pwd = os.getenv("SHOONYA_PWD")
api_key = os.getenv("SHOONYA_API_KEY")
totp_seed = os.getenv("SHOONYA_TOTP")
vendor = os.getenv("SHOONYA_VENDOR")
imei = os.getenv("SHOONYA_IMEI", "abc1234")

logger.info(f"Testing login for {user}")
logger.info(f"Vendor: {vendor}")
logger.info(f"IMEI: {imei}")

otp = totp_from_seed(totp_seed)
logger.info(f"Generated OTP: {otp}")

api = NorenApi(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')

try:
    print("\n--- ATTEMPTING LOGIN ---")
    ret = api.login(
        userid=user,
        password=pwd,
        twoFA=otp,
        vendor_code=vendor,
        api_secret=api_key,
        imei=imei
    )
    print("Response:", ret)
    if ret and ret.get('stat') == 'Ok':
        print("✅ SUCCESS")
    else:
        print("❌ FAILED")
except Exception as e:
    print("💥 EXCEPTION:", e)
    import traceback
    traceback.print_exc()
