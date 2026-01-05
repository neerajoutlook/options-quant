#!/usr/bin/env python3
"""
Compare credentials byte-by-byte
"""
import os
from dotenv import dotenv_values

path_quant = "/Users/neerajsharma/personal/python-projects/options-quant/.env"
path_nifty = "/Users/neerajsharma/personal/python-projects/nifty_algo/.env"

env_quant = dotenv_values(path_quant)
env_nifty = dotenv_values(path_nifty)

key_quant = env_quant.get("SHOONYA_API_KEY")
key_nifty = env_nifty.get("SHOONYA_API_SECRET")

user_quant = env_quant.get("SHOONYA_USER")
user_nifty = env_nifty.get("SHOONYA_USER_ID")

print(f"Quant Key: >{key_quant}< (len={len(key_quant)})")
print(f"Nifty Key: >{key_nifty}< (len={len(key_nifty)})")

print(f"Quant User: >{user_quant}< (len={len(user_quant)})")
print(f"Nifty User: >{user_nifty}< (len={len(user_nifty)})")

if key_quant == key_nifty and user_quant == user_nifty:
    print("EVERYTHING MATCHES!")
else:
    print("MISMATCH FOUND!")
    if user_quant != user_nifty:
        print("User mismatch!")
    # diff
import hashlib

def get_hash(uid, key):
    return hashlib.sha256((uid + "|" + key).encode()).hexdigest()

hash_quant = get_hash(user_quant, key_quant)
hash_nifty = get_hash(user_nifty, key_nifty)

print(f"Quant Hash: {hash_quant}")
print(f"Nifty Hash: {hash_nifty}")
