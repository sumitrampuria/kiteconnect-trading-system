#!/usr/bin/env python3
"""
Main entry point for the project.
"""
import logging
import os
import sys
import json
import datetime
import re
from kiteconnect import KiteConnect, KiteTicker


try:
    with open("Login Credentials.json", "r") as f:
        login_credential = json.load(f)
except:
    try:
        with open("credentials.txt", "r") as cred_file:
            raw = cred_file.read().strip()
        api_key_val = None
        api_secret_val = None
        non_comment_lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            non_comment_lines.append(stripped)
            if "=" in stripped:
                key, value = stripped.split("=", 1)
                key = key.strip().lower()
                value = value.strip()
                if key == "api_key":
                    api_key_val = value
                elif key == "api_secret":
                    api_secret_val = value
        if not api_key_val or not api_secret_val:
            if len(non_comment_lines) >= 2:
                api_key_val = api_key_val or non_comment_lines[0]
                api_secret_val = api_secret_val or non_comment_lines[1]
        if not api_key_val or not api_secret_val:
            raise ValueError("credentials.txt is missing api_key or api_secret")
        login_credential = {
            "api_key": api_key_val,
            "api_secret": api_secret_val
        }
    except Exception as e:
        print(f"Failed to load credentials from credentials.txt: {e}")
        sys.exit(1)


print("---Getting Access Token---")
if os.path.exists(f"AccessToken/{datetime.datetime.now().date()}.json"):
    with open(f"AccessToken/{datetime.datetime.now().date()}.json", "r") as f:
        access_token = json.load(f)
        kite = KiteConnect(api_key=login_credential["api_key"])
        kite.set_access_token(access_token)
else:
    print("Trying Log In...")
    kite = KiteConnect(api_key=login_credential["api_key"])
    print("Login url : ", kite.login_url())
    request_tkn = input("Login and enter your 'request token' here : ")
    try:
        access_token = kite.generate_session(request_token=request_tkn,
                                            api_secret=login_credential["api_secret"])['access_token']
        os.makedirs(f"AccessToken", exist_ok=True)
        with open(f"AccessToken/{datetime.datetime.now().date()}.json", "w") as f:
            json.dump(access_token, f)
        print("Login successful...")
    except Exception as e:
        print(f"Login Failed {{{e}}}")
        sys.exit()

print(f"API Key : {login_credential['api_key']}")
print(f"Access Token : {access_token}")
print()


instruments = kite.instruments()
orders = kite.orders()

# Finding the NIFTY spot price (LTP)
symbol = "NIFTY 50"
temp = f"NSE:{symbol}"
nifty_ltp = kite.quote(temp)[temp]["last_price"]
print("Nifty LTP: ", nifty_ltp)


def get_nifty_instruments_near_spot(instrument_dump, nifty_ltp_value, max_diff=50):
    """
    Return only those NIFTY instruments whose strike price is within
    +/- max_diff points of the NIFTY spot price (nifty_ltp_value).

    Identification rules:
    - tradingsymbol contains 'NIFTY'
    - tradingsymbol does NOT contain 'FIN', 'NXT', 'MID', or 'BANK'
    - strike price parsed from tradingsymbol (e.g. NIFTY25D2326200CE -> 26200)
      is within +/- max_diff of nifty_ltp_value
    """
    result = []

    for inst in instrument_dump:
        ts = inst.get("tradingsymbol", "")
        if not isinstance(ts, str):
            continue

        upper_ts = ts.upper()

        # Must be NIFTY but not FIN, NXT, MID, BANK variants
        if (
            "NIFTY" not in upper_ts
            or "FIN" in upper_ts
            or "NXT" in upper_ts
            or "MID" in upper_ts
            or "BANK" in upper_ts
        ):
            continue

        # Extract strike price from the symbol (e.g. ...26200CE / ...26200PE)
        m = re.search(r"(\d+)(CE|PE)$", upper_ts)
        if not m:
            continue

        try:
            strike = float(m.group(1))
        except ValueError:
            continue

        if abs(strike - float(nifty_ltp_value)) <= max_diff:
            result.append(inst)

    return result


instrument_dump = kite.instruments("NFO")

# Collect resultant instruments here
resultant_instruments = get_nifty_instruments_near_spot(
    instrument_dump,
    nifty_ltp,
    max_diff=50,
)

print("Filtered NIFTY instruments near spot (+/- 50):")
print(resultant_instruments)


kws = KiteTicker(login_credential['api_key'], access_token)


print("placing the order")
kite.place_order(
    variety="regular",
    exchange="NFO",
    tradingsymbol="NIFTY25D2326200CE", 
    transaction_type="SELL",
    order_type="LIMIT",
    quantity=75,
    product="NRML",
    price=150.00,
    validity="DAY"
)

def on_ticks(ws, ticks):
    # Callback to receive ticks.
    print("printing ticks")
    print("Ticks: {}".format(ticks))

def on_connect(ws, response):
    # Callback on successful connect.
    # Subscribe to a list of instrument_tokens (RELIANCE and ACC here).
    print("Subscription")
    ws.subscribe([14597122])

    # Set RELIANCE to tick in `full` mode.
    ws.set_mode(ws.MODE_FULL, [14597122])

def on_close(ws, code, reason):
    # On connection close stop the main loop
    # Reconnection will not happen after executing `ws.stop()`
    ws.stop()

# Assign the callbacks.
kws.on_ticks = on_ticks
kws.on_connect = on_connect
kws.on_close = on_close

# Infinite loop on the main thread. Nothing after this will run.
# You have to use the pre-defined callbacks to manage subscriptions.
# 

kws.connect()




