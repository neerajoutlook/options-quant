from core.config import SHOONYA_TOTP
print(f"TOTP Secret: '{SHOONYA_TOTP}'")
print(f"TOTP Secret Length: {len(SHOONYA_TOTP)}")
print(f"Has quotes: {SHOONYA_TOTP.startswith(chr(34))}")
