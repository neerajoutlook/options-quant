import sys
sys.path.append("/Users/neerajsharma/personal/python-projects/trading-software")

# First try remote
from config.config import SHOONYA_TOTP as remote_totp, SHOONYA_USER as remote_user

# Remove from path
sys.path.remove("/Users/neerajsharma/personal/python-projects/trading-software")

# Now try local
from core.config import SHOONYA_TOTP as local_totp, SHOONYA_USER as local_user

print(f"Remote TOTP[0:10]: {remote_totp[0:10]}")
print(f"Local TOTP[0:10]: {local_totp[0:10]}")
print(f"Match: {remote_totp == local_totp}")

print(f"\nRemote USER: {remote_user}")
print(f"Local USER: {local_user}")
print(f"Match: {remote_user == local_user}")
