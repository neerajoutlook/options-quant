import logging
import sys
from core.shoonya_client import ShoonyaSession, totp_from_seed
from core.config import SHOONYA_USER, SHOONYA_PWD, SHOONYA_API_KEY, SHOONYA_TOTP, SHOONYA_VENDOR

# Configure Logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)

def test_login():
    print(f"User: {SHOONYA_USER}")
    print(f"Pwd: {'*' * len(SHOONYA_PWD) if SHOONYA_PWD else 'None'}")
    print(f"API Key: {'*' * len(SHOONYA_API_KEY) if SHOONYA_API_KEY else 'None'}")
    print(f"TOTP Secret: {'*' * len(SHOONYA_TOTP) if SHOONYA_TOTP else 'None'}")
    print(f"Vendor: {SHOONYA_VENDOR}")
    
    otp = totp_from_seed(SHOONYA_TOTP)
    print(f"Generated OTP: {otp}")
    
    session = ShoonyaSession()
    try:
        ret = session.login()
        print(f"Login Result: {ret}")
    except Exception as e:
        print(f"Login Failed: {e}")

if __name__ == "__main__":
    test_login()
