import time
import hmac
import hashlib
import requests
import os
from urllib.parse import urlencode

# -----------------------------------------------------------
# CONFIG (Cursor will ask user to fill this or read from env)
# -----------------------------------------------------------
# Try to get from env, otherwise placeholders
API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_API_KEY_HERE")
API_SECRET = os.getenv("BINANCE_API_SECRET", "YOUR_SECRET_KEY_HERE")

def send_signed_request(base_url, endpoint, method="GET", payload={}):
    if "YOUR_" in API_KEY:
        print("❌ ERROR: Please edit the file and insert your API_KEY and API_SECRET")
        return {"code": -1}

    query_string = urlencode(payload)
    if query_string:
        query_string = "{}&timestamp={}".format(query_string, int(time.time() * 1000))
    else:
        query_string = "timestamp={}".format(int(time.time() * 1000))

    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}

    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        else:
            response = requests.post(url, headers=headers)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

print("="*50)
print("🔍 BINANCE PERMISSION DIAGNOSTICS")
print("="*50)

# 1. TEST FUTURES
print("\n1️⃣ Testing FUTURES API (/fapi/v2/account)...")
futures_response = send_signed_request("https://fapi.binance.com", "/fapi/v2/account")

if "code" in futures_response and futures_response["code"] != 0:
    print(f"❌ FUTURES ERROR: {futures_response}")
else:
    print("✅ FUTURES API WORKS! (You have Futures Trading permissions)")

print("-" * 50)

# 2. TEST SPOT
print("\n2️⃣ Testing SPOT API (/api/v3/account)...")
spot_response = send_signed_request("https://api.binance.com", "/api/v3/account")

if "code" in spot_response and spot_response["code"] != 0:
    print(f"❌ SPOT ERROR: {spot_response}")
    if spot_response.get('code') == -2015:
        print("\n🚨 DIAGNOSIS FOUND:")
        print("   The bot is crashing because it checks Spot balance/connection.")
        print("   SOLUTION: Go to Binance API settings and enable 'Enable Spot & Margin Trading'.")
else:
    print("✅ SPOT API WORKS! (General account access is OK)")

print("\n" + "="*50)
