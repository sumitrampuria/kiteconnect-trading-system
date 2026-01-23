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
import urllib.parse
from kiteconnect import KiteConnect, KiteTicker
from google_sheets_reader import get_all_accounts_from_google_sheet


# Read all accounts from Google Sheets
print("---Reading all accounts from Google Sheets---")
try:
    accounts = get_all_accounts_from_google_sheet(
        spreadsheet_id="1bz-TvpcGnUpzD59sPnbLOtjrRpb4U4v_B-Pohgd3ZU4",
        gid=736151233,  # GID from the URL
        header_row=7,   # Headers are in row 7
        data_start_row=8  # Data starts from row 8
    )

    # Treat row 8 (first data row) as the BASE ACCOUNT
    if accounts:
        accounts[0]["is_base_account"] = True
    for idx in range(1, len(accounts)):
        accounts[idx]["is_base_account"] = False

    def display_account_name(account: dict) -> str:
        name = account.get("account_holder_name", "Unknown")
        return f"BASE ACCOUNT {name}" if account.get("is_base_account") else name

    print(f"\nSuccessfully retrieved {len(accounts)} account(s) from Google Sheets")
    
    # Print summary header
    print("\n" + "="*80)
    print("ALL ACCOUNT DETAILS")
    print("="*80)
    
    # Display all accounts with detailed information
    for i, account in enumerate(accounts, 1):
        print(f"\n{'─'*80}")
        print(f"ACCOUNT #{i}")
        print(f"{'─'*80}")
        print(f"  Account Holder Name    : {display_account_name(account)}")
        print(f"  Account KITE-ID        : {account.get('account_kite_id', 'N/A')}")
        print(f"  API Key                 : {account.get('api_key', 'N/A')}")
        api_secret = account.get('api_secret', '')
        if api_secret:
            print(f"  API Secret              : {'*' * len(api_secret)} ({len(api_secret)} characters)")
        else:
            print(f"  API Secret              : N/A")
        request_url = account.get('request_url_by_zerodha', 'N/A')
        if request_url and request_url != 'None':
            print(f"  Request URL by Zerodha  : {request_url}")
        else:
            print(f"  Request URL by Zerodha  : Not available")
        print(f"{'─'*80}")
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"SUMMARY: Total {len(accounts)} account(s) loaded")
    print(f"{'='*80}")
    
    # Print accounts array structure for reference
    print("\nAccounts array structure:")
    print(f"  Type: {type(accounts)}")
    print(f"  Length: {len(accounts)}")
    print(f"  Keys in each account: {list(accounts[0].keys()) if accounts else 'No accounts'}")
    
    # Print all account details in a compact format
    print("\n" + "="*80)
    print("ACCOUNTS ARRAY CONTENTS")
    print("="*80)
    for i, account in enumerate(accounts, 1):
        print(f"\nAccount[{i-1}]:")
        for key, value in account.items():
            if key == 'api_secret' and value:
                print(f"  '{key}': {'*' * len(value)}")
            else:
                print(f"  '{key}': {value}")
    
    # For now, use the first account's credentials (you can modify this logic)
    if accounts and accounts[0].get('api_key') and accounts[0].get('api_secret'):
        login_credential = {
            "api_key": accounts[0]['api_key'],
            "api_secret": accounts[0]['api_secret']
        }
        print(f"\nUsing credentials from: {display_account_name(accounts[0])}")
    else:
        raise ValueError("No valid account credentials found in the sheet")
    
    # Print the accounts array
    print("\n" + "="*80)
    print("ACCOUNTS ARRAY (Raw Output)")
    print("="*80)
    print(accounts)
    print("\n" + "="*80)
    print("ACCOUNTS ARRAY (JSON Formatted)")
    print("="*80)
    # Create a copy with masked secrets for JSON output
    accounts_for_display = []
    for account in accounts:
        account_copy = account.copy()
        if account_copy.get('api_secret'):
            account_copy['api_secret'] = '*' * len(account_copy['api_secret'])
        accounts_for_display.append(account_copy)
    print(json.dumps(accounts_for_display, indent=2))
    print("="*80)
        
except Exception as e:
    print(f"Failed to read from Google Sheets: {e}")
    print("Falling back to local credentials...")
    # Fallback to local credentials if Google Sheets fails
    try:
        with open("credentials.txt", "r") as cred_file:
            raw = cred_file.read().strip()
        api_key_val = None
        api_secret_val = None
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key, value = stripped.split("=", 1)
                key = key.strip().lower()
                value = value.strip()
                if key == "api_key":
                    api_key_val = value
                elif key == "api_secret":
                    api_secret_val = value
        if not api_key_val or not api_secret_val:
            raise ValueError("credentials.txt is missing api_key or api_secret")
        login_credential = {
            "api_key": api_key_val,
            "api_secret": api_secret_val
        }
        # Create a single-account array for consistency
        accounts = [{
            "account_holder_name": "Local",
            "account_kite_id": "N/A",
            "api_key": api_key_val,
            "api_secret": api_secret_val,
            "request_url_by_zerodha": None,
            "is_base_account": True
        }]
        def display_account_name(account: dict) -> str:
            name = account.get("account_holder_name", "Unknown")
            return f"BASE ACCOUNT {name}" if account.get("is_base_account") else name
    except Exception as e2:
        print(f"Failed to load credentials from credentials.txt: {e2}")
        sys.exit(1)


# Create KiteConnect instance for each account
print("\n" + "="*80)
print("INITIALIZING KITECONNECT FOR EACH ACCOUNT")
print("="*80)

def initialize_kite_for_account(account):
    """
    Initialize KiteConnect instance for a single account.
    
    Args:
        account: Dictionary containing account details with api_key, api_secret, etc.
    
    Returns:
        KiteConnect instance or None if initialization fails
    """
    account_name = display_account_name(account)
    account_kite_id = account.get('account_kite_id', 'Unknown')
    api_key = account.get('api_key')
    api_secret = account.get('api_secret')
    
    if not api_key or not api_secret:
        print(f"\n⚠️  Skipping {account_name} ({account_kite_id}): Missing API credentials")
        return None
    
    print(f"\n{'─'*80}")
    print(f"Initializing KiteConnect for: {account_name} ({account_kite_id})")
    print(f"{'─'*80}")
    
    try:
        # Create KiteConnect instance with account's API key
        kite = KiteConnect(api_key=api_key)
        print(f"✓ Created KiteConnect instance with API Key: {api_key}")
        
        # Try to load existing access token (per account, per date)
        access_token_file = f"AccessToken/{account_kite_id}_{datetime.datetime.now().date()}.json"
        
        if os.path.exists(access_token_file):
            print(f"✓ Found existing access token file: {access_token_file}")
            with open(access_token_file, "r") as f:
                access_token = json.load(f)
            kite.set_access_token(access_token)
            print(f"✓ Access token loaded and set successfully")
            print(f"\n🎉 KiteConnect connection established for: {account_name} ({account_kite_id})")
            return kite
        else:
            print(f"⚠️  No existing access token found at: {access_token_file}")
            
            # Try to extract request token from request_url_by_zerodha if available
            request_url = account.get('request_url_by_zerodha')
            request_token = None
            
            if request_url and request_url != 'None' and 'request_token=' in request_url:
                try:
                    # Extract request_token from URL
                    parsed_url = urllib.parse.urlparse(request_url)
                    params = urllib.parse.parse_qs(parsed_url.query)
                    if 'request_token' in params:
                        request_token = params['request_token'][0]
                        print(f"✓ Extracted request token from URL")
                except Exception as e:
                    print(f"⚠️  Could not extract request token from URL: {e}")
            
            if request_token:
                try:
                    print(f"✓ Generating session with request token...")
                    access_token = kite.generate_session(
                        request_token=request_token,
                        api_secret=api_secret
                    )['access_token']
                    
                    # Save access token
                    os.makedirs("AccessToken", exist_ok=True)
                    with open(access_token_file, "w") as f:
                        json.dump(access_token, f)
                    
                    kite.set_access_token(access_token)
                    print(f"✓ Session generated and access token saved successfully")
                    print(f"\n🎉 KiteConnect connection established for: {account_name} ({account_kite_id})")
                    return kite
                except Exception as e:
                    print(f"✗ Failed to generate session: {e}")
                    print(f"  ⚠️  The request token in the Google Sheet has expired.")
                    print(f"  📝 To fix this:")
                    print(f"     1. Visit the login URL: {kite.login_url()}")
                    print(f"     2. Complete the login process")
                    print(f"     3. Copy the redirect URL (contains request_token)")
                    print(f"     4. Update the 'Request URL by Zerodha' column in Google Sheet")
                    print(f"     5. Run this script again")
                    return None
            else:
                print(f"⚠️  No request token available. Manual login required.")
                print(f"  Login URL: {kite.login_url()}")
                print(f"  After logging in, extract the request_token from the redirect URL")
                print(f"  and update the 'Request URL by Zerodha' column in the Google Sheet")
                return None
                
    except Exception as e:
        print(f"✗ Failed to initialize KiteConnect for {account_name}: {e}")
        return None


# Initialize KiteConnect for each account
for i, account in enumerate(accounts):
    kite_instance = initialize_kite_for_account(account)
    if kite_instance:
        # Add kite instance to the account dictionary
        account['kite'] = kite_instance
        print(f"✓ KiteConnect instance added to account {i+1}")
    else:
        account['kite'] = None
        print(f"✗ KiteConnect instance not available for account {i+1}")

# Print summary of initialized accounts
print("\n" + "="*80)
print("KITECONNECT INITIALIZATION SUMMARY")
print("="*80)
initialized_count = sum(1 for acc in accounts if acc.get('kite') is not None)
print(f"Total accounts: {len(accounts)}")
print(f"Successfully initialized: {initialized_count}")
print(f"Failed/Not initialized: {len(accounts) - initialized_count}")

for i, account in enumerate(accounts, 1):
    status = "✓ Ready" if account.get('kite') else "✗ Not Ready"
    print(f"  Account {i} ({display_account_name(account)}): {status}")
print("="*80)


# Fetch and display open positions for each account
print("\n" + "="*80)
print("FETCHING OPEN POSITIONS FOR EACH ACCOUNT")
print("="*80)

def get_positions_for_account(account):
    """
    Fetch and return positions for an account.
    
    Args:
        account: Dictionary containing account details with kite instance
    
    Returns:
        Dictionary with positions data or None if failed
    """
    kite = account.get('kite')
    if not kite:
        return None
    
    try:
        positions = kite.positions()
        return positions
    except Exception as e:
        print(f"✗ Error fetching positions: {e}")
        return None


def print_positions_for_account(account, positions):
    """
    Print positions in a formatted way for an account.
    
    Args:
        account: Dictionary containing account details
        positions: Positions data from KiteConnect API
    """
    account_name = display_account_name(account)
    account_kite_id = account.get('account_kite_id', 'Unknown')
    
    print(f"\n{'─'*80}")
    print(f"POSITIONS FOR: {account_name} ({account_kite_id})")
    print(f"{'─'*80}")
    
    if not positions:
        print("  No positions data available")
        return
    
    # KiteConnect positions API returns a dict with 'net' and 'day' keys
    # 'net' contains all positions (both day and carry-forward)
    # 'day' contains only day positions
    
    net_positions = positions.get('net', [])
    day_positions = positions.get('day', [])
    
    if not net_positions:
        print("  ✓ No positions")
        return
    
    # Include BOTH open and closed/booked positions
    all_positions = net_positions
    open_positions = [pos for pos in all_positions if pos.get('quantity', 0) != 0]
    closed_positions = [pos for pos in all_positions if pos.get('quantity', 0) == 0]
    
    print(f"\n  Total Positions: {len(all_positions)} (Open: {len(open_positions)}, Closed: {len(closed_positions)})")
    print(
        f"\n  {'Status':<8} {'Symbol':<20} {'Exchange':<10} {'Product':<10} "
        f"{'Quantity':<12} {'Avg Price':<12} {'LTP':<12} {'P&L':<15}"
    )
    print(f"  {'-'*8} {'-'*20} {'-'*10} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*15}")
    
    total_pnl = 0
    for pos in all_positions:
        symbol = pos.get('tradingsymbol', 'N/A')
        exchange = pos.get('exchange', 'N/A')
        product = pos.get('product', 'N/A')
        quantity = pos.get('quantity', 0)
        avg_price = pos.get('average_price', 0)
        ltp = pos.get('last_price', 0)
        pnl = pos.get('pnl', 0)
        total_pnl += pnl
        
        # Format values
        qty_str = f"{quantity:+.0f}" if quantity != 0 else "0"
        avg_price_str = f"{avg_price:.2f}" if avg_price else "0.00"
        ltp_str = f"{ltp:.2f}" if ltp else "0.00"
        pnl_str = f"₹{pnl:+.2f}" if pnl else "₹0.00"
        
        # Color code P&L (positive/negative) - show in raw format
        if pnl > 0:
            pnl_display = f"✓ {pnl_str}"
        elif pnl < 0:
            pnl_display = f"✗ {pnl_str}"
        else:
            pnl_display = pnl_str
        
        status = "OPEN" if quantity != 0 else "CLOSED"
        print(f"  {status:<8} {symbol:<20} {exchange:<10} {product:<10} {qty_str:<12} {avg_price_str:<12} {ltp_str:<12} {pnl_display:<15}")
    
    print(f"\n  {'-'*100}")
    total_pnl_str = f"₹{total_pnl:+.2f}"
    if total_pnl > 0:
        total_pnl_display = f"✓ Total P&L: {total_pnl_str}"
    elif total_pnl < 0:
        total_pnl_display = f"✗ Total P&L: {total_pnl_str}"
    else:
        total_pnl_display = f"Total P&L: {total_pnl_str}"
    print(f"  {total_pnl_display}")
    print(f"{'─'*80}")


# Fetch and print positions for each account
for i, account in enumerate(accounts, 1):
    account_name = account.get('account_holder_name', 'Unknown')
    kite = account.get('kite')
    
    if not kite:
        print(f"\n{'─'*80}")
        print(f"POSITIONS FOR: {account_name}")
        print(f"{'─'*80}")
        print("  ✗ Cannot fetch positions - KiteConnect not initialized")
        print(f"{'─'*80}")
        continue
    
    try:
        positions = get_positions_for_account(account)
        print_positions_for_account(account, positions)
    except Exception as e:
        print(f"\n{'─'*80}")
        print(f"POSITIONS FOR: {account_name}")
        print(f"{'─'*80}")
        print(f"  ✗ Error: {e}")
        print(f"{'─'*80}")

print("\n" + "="*80)
print("POSITIONS FETCH COMPLETE")
print("="*80)


# Fetch and display margins for each account
print("\n" + "="*80)
print("FETCHING MARGINS FOR EACH ACCOUNT")
print("="*80)


def _safe_float(val):
    try:
        return float(val)
    except Exception:
        return None


def get_margins_for_account(account):
    """
    Fetch and return margins for an account.

    Returns:
        Dict (KiteConnect margins payload) or None
    """
    kite = account.get("kite")
    if not kite:
        return None
    try:
        return kite.margins()  # KiteConnect REST API: GET /margins
    except Exception as e:
        print(f"✗ Error fetching margins: {e}")
        return None


def print_margins_for_account(account, margins):
    account_name = display_account_name(account)
    account_kite_id = account.get("account_kite_id", "Unknown")

    print(f"\n{'─'*80}")
    print(f"MARGINS FOR: {account_name} ({account_kite_id})")
    print(f"{'─'*80}")

    if not margins:
        print("  No margins data available")
        return

    # We only care about EQUITY margin
    seg = margins.get("equity")
    if not isinstance(seg, dict):
        print("  No equity margins data available")
        print(f"{'─'*80}")
        return

    # Your expected "available margin" matches Kite's equity.net
    # (also equals: (available.cash + available.collateral + available.adhoc_margin + available.intraday_payin) - utilised.debits)
    available = _safe_float(seg.get("net"))

    # Used margin from utilised.debits (this represents funds blocked/used)
    used = _safe_float(seg.get("utilised", {}).get("debits"))

    # Total = Available + Used (per your requirement)
    total = (available + used) if (available is not None and used is not None) else None

    def _fmt_money(x):
        # x is rupees; print in crores
        if not isinstance(x, (int, float)):
            return "N/A"
        return f"₹{(x/1e7):.4f} Cr"

    print(f"  Total Margin     : {_fmt_money(total)}")
    print(f"  Available Margin : {_fmt_money(available)}")
    print(f"  Used Margin      : {_fmt_money(used)}")

    print(f"{'─'*80}")


for account in accounts:
    if not account.get("kite"):
        print(f"\n{'─'*80}")
        print(f"MARGINS FOR: {account.get('account_holder_name', 'Unknown')}")
        print(f"{'─'*80}")
        print("  ✗ Cannot fetch margins - KiteConnect not initialized")
        print(f"{'─'*80}")
        continue

    margins = get_margins_for_account(account)
    print_margins_for_account(account, margins)

print("\n" + "="*80)
print("MARGINS FETCH COMPLETE")
print("="*80)






