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
import math
from kiteconnect import KiteConnect, KiteTicker
from google_sheets_reader import get_all_accounts_from_google_sheet
# Load lot sizes and max quantity (used to compute P&L for derivatives)
try:
    with open("lot_sizes_config.json", "r") as f:
        lot_sizes_config = json.load(f)
    lot_sizes = lot_sizes_config.get("lot_sizes", {})
    max_quantity = lot_sizes_config.get("max_quantity", {})
except:
    lot_sizes = {"NFO": 65, "BFO": 20}
    max_quantity = {"NFO": 1755, "BFO": 2000}


def _compute_ltp_and_pnl(kite, pos):
    """
    Fetch live LTP for a position and compute P&L locally using lot size.
    Returns (ltp, pnl)
    """
    symbol = pos.get('tradingsymbol', '')
    exchange = (pos.get('exchange') or '').upper()
    avg_price = pos.get('average_price', 0) or 0
    quantity = pos.get('quantity', 0) or 0

    # (no per-instrument lot multiplier used here)

    # Start with the LTP provided in the position object as fallback
    ltp = pos.get('last_price', 0) or 0
    try:
        if symbol and exchange:
            quote_key = f"{exchange}:{symbol}"
            quote_data = kite.quote([quote_key])
            if quote_data and quote_key in quote_data:
                ltp = quote_data[quote_key].get('last_price', ltp)
    except Exception:
        # ignore quote errors and keep fallback LTP
        pass

    # Compute P&L: (LTP - Avg Price) * Quantity (positive when market price > avg for long)
    try:
        pnl = (ltp - avg_price) * quantity
    except Exception:
        pnl = 0

    return ltp, pnl
def get_trading_mechanism_from_sheet(spreadsheet_id, gid):
    """Get Trading Mechanism value from row 4, cell B4."""
    import gspread
    from google.oauth2.service_account import Credentials
    
    scope = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    client = None
    
    # Try service account file
    default_paths = ['service_account.json', 'credentials.json', 'google_credentials.json']
    for path in default_paths:
        if os.path.exists(path):
            creds = Credentials.from_service_account_file(path, scopes=scope)
            client = gspread.authorize(creds)
            break
    
    if client is None:
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            creds = Credentials.from_service_account_file(
                os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), scopes=scope
            )
            client = gspread.authorize(creds)
    
    if client is None:
        return None
    
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        if gid:
            worksheet = spreadsheet.get_worksheet_by_id(int(gid))
        else:
            worksheet = spreadsheet.sheet1
        
        # Read cell B4 (row 4, column 2)
        cell_b4 = worksheet.cell(4, 2).value
        if cell_b4:
            value_upper = str(cell_b4).strip().upper()
            if value_upper in ["BUTTON BASED", "AUTO"]:
                return value_upper
        
        # Fallback: search row 4 for "Button Based" or "Auto"
        row_values = worksheet.row_values(4)
        for value in row_values:
            if value:
                value_upper = str(value).strip().upper()
                if value_upper in ["BUTTON BASED", "AUTO"]:
                    return value_upper
        
        return None
    except Exception as e:
        print(f"Warning: Could not read Trading Mechanism: {e}")
        return None


# Read all accounts from Google Sheets
print("---Reading all accounts from Google Sheets---")
try:
    accounts = get_all_accounts_from_google_sheet(
        spreadsheet_id="1h9r9DyHgXX39EysPEzZDn70mBM7jQa-I1l8u6bl92M4",
        gid=736151233,  # GID from the URL
        header_row=7,   # Headers are in row 7
        data_start_row=8  # Data starts from row 8
    )
    
    # Get Trading Mechanism from row 4
    trading_mechanism = get_trading_mechanism_from_sheet(
        spreadsheet_id="1h9r9DyHgXX39EysPEzZDn70mBM7jQa-I1l8u6bl92M4",
        gid=736151233
    )
    if not trading_mechanism:
        trading_mechanism = "BUTTON BASED"  # Default
        print("⚠️  Warning: Trading Mechanism not found. Defaulting to 'BUTTON BASED'")
    else:
        print(f"✓ Trading Mechanism: {trading_mechanism}")

    # Determine base account from "Copy Trades" column (value = "Base")
    # If no account has "Copy Trades" = "Base", default to first account
    base_account_found = False
    for account in accounts:
        copy_trades = str(account.get('copy_trades', '')).strip().upper()
        if copy_trades == 'BASE':
            account["is_base_account"] = True
            base_account_found = True
        else:
            account["is_base_account"] = False
    
    # If no account marked as "Base", default to first account
    if not base_account_found and accounts:
        accounts[0]["is_base_account"] = True
        print("⚠️  Warning: No account found with 'Copy Trades' = 'Base'. Using first account as base.")

    # Save account config to local file
    config_data = {
        "trading_mechanism": trading_mechanism,
        "accounts": []
    }
    
    for account in accounts:
        account_config = {
            "account_holder_name": account.get("account_holder_name"),
            "account_kite_id": account.get("account_kite_id"),
            "copy_trades": account.get("copy_trades", "NO"),
            "api_key": account.get("api_key"),
            "api_secret": account.get("api_secret"),
            "request_url_by_zerodha": account.get("request_url_by_zerodha"),
            "is_base_account": account.get("is_base_account", False)
        }
        config_data["accounts"].append(account_config)
    
    config_file = "accounts_config.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)
    print(f"✓ Saved account configuration to {config_file}")

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
    
    # For now, use the first account's credentials (you can modify this logic)
    if accounts and accounts[0].get('api_key') and accounts[0].get('api_secret'):
        login_credential = {
            "api_key": accounts[0]['api_key'],
            "api_secret": accounts[0]['api_secret']
        }
        print(f"\nUsing credentials from: {display_account_name(accounts[0])}")
    else:
        raise ValueError("No valid account credentials found in the sheet")
        
except Exception as e:
    print(f"Failed to read from Google Sheets: {e}")
    print("Please ensure Google Sheets is accessible and service account is configured correctly.")
    sys.exit(1)


# Helper function to get account status for display
def get_account_status(account):
    """
    Get the account status for display.
    
    Returns:
        str: "BASE ACCOUNT", "Sync On", or "Sync Off"
    """
    copy_trades = str(account.get('copy_trades', '')).strip().upper()
    if copy_trades == 'BASE' or account.get('is_base_account'):
        return "BASE ACCOUNT"
    elif copy_trades == 'YES':
        return "Sync On"
    else:
        return "Sync Off"


# Create KiteConnect instance for each account
# Check if this is first run (all accounts have access tokens) or subsequent run
def check_if_first_run():
    """Check if this is the first run by seeing if access tokens exist for all accounts."""
    today = datetime.datetime.now().date()
    token_files_exist = 0
    for account in accounts:
        account_kite_id = account.get('account_kite_id', '')
        if account_kite_id:
            token_file = f"AccessToken/{account_kite_id}_{today}.json"
            if os.path.exists(token_file):
                token_files_exist += 1
    # If all accounts have tokens, it's not the first run
    return token_files_exist < len(accounts) or token_files_exist == 0

is_first_run = check_if_first_run()

if is_first_run:
    print("\n" + "="*80)
    print("INITIALIZING KITECONNECT FOR EACH ACCOUNT")
    print("="*80)
else:
    print("\n" + "="*80)
    print("REINITIALIZING KITECONNECT CONNECTIONS (QUIET MODE)")
    print("="*80)

def initialize_kite_for_account(account, verbose=True):
    """
    Initialize KiteConnect instance for a single account.
    
    Args:
        account: Dictionary containing account details with api_key, api_secret, etc.
        verbose: If False, suppress detailed output (for subsequent runs)
    
    Returns:
        KiteConnect instance or None if initialization fails
    """
    account_name = display_account_name(account)
    account_kite_id = account.get('account_kite_id', 'Unknown')
    api_key = account.get('api_key')
    api_secret = account.get('api_secret')
    
    if not api_key or not api_secret:
        if verbose:
            print(f"\n⚠️  Skipping {account_name} ({account_kite_id}): Missing API credentials")
        return None
    
    if verbose:
        print(f"\n{'─'*80}")
        print(f"Initializing KiteConnect for: {account_name} ({account_kite_id})")
        print(f"{'─'*80}")
    
    try:
        # Create KiteConnect instance with account's API key
        kite = KiteConnect(api_key=api_key)
        if verbose:
            print(f"✓ Created KiteConnect instance with API Key: {api_key}")
        
        # Try to load existing access token (per account, per date)
        access_token_file = f"AccessToken/{account_kite_id}_{datetime.datetime.now().date()}.json"
        
        if os.path.exists(access_token_file):
            if verbose:
                print(f"✓ Found existing access token file: {access_token_file}")
            with open(access_token_file, "r") as f:
                access_token = json.load(f)
            kite.set_access_token(access_token)
            if verbose:
                print(f"✓ Access token loaded and set successfully")
                print(f"\n🎉 KiteConnect connection established for: {account_name} ({account_kite_id})")
            return kite
        else:
            if verbose:
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
                        if verbose:
                            print(f"✓ Extracted request token from URL")
                except Exception as e:
                    if verbose:
                        print(f"⚠️  Could not extract request token from URL: {e}")
            
            if request_token:
                try:
                    if verbose:
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
                    if verbose:
                        print(f"✓ Session generated and access token saved successfully")
                        print(f"\n🎉 KiteConnect connection established for: {account_name} ({account_kite_id})")
                    return kite
                except Exception as e:
                    error_msg = str(e)
                    # Always show errors, even in quiet mode
                    print(f"✗ Failed to generate session for {account_name}: {error_msg}")
                    
                    if verbose:
                        if "invalid" in error_msg.lower() or "expired" in error_msg.lower():
                            print(f"  ⚠️  The request token in the Google Sheet has expired or is invalid.")
                            print(f"  📝 To fix this:")
                            print(f"     1. Visit the login URL: {kite.login_url()}")
                            print(f"     2. Complete the login process")
                            print(f"     3. Copy the redirect URL (contains request_token)")
                            print(f"     4. Update the 'Request URL by Zerodha' column in Google Sheet")
                            print(f"     5. Run this script again")
                            print(f"  💡 Tip: Request tokens expire quickly. Generate a fresh token right before running the script.")
                        else:
                            print(f"  ⚠️  Unexpected error during session generation.")
                            print(f"  📝 Please check:")
                            print(f"     - API key and secret are correct")
                            print(f"     - Request token is valid and not expired")
                            print(f"     - Internet connection is stable")
                    return None
            else:
                if verbose:
                    print(f"⚠️  No request token available. Manual login required.")
                    print(f"  Login URL: {kite.login_url()}")
                    print(f"  After logging in, extract the request_token from the redirect URL")
                    print(f"  and update the 'Request URL by Zerodha' column in the Google Sheet")
                return None
                
    except Exception as e:
        # Always show errors
        print(f"✗ Failed to initialize KiteConnect for {account_name}: {e}")
        return None


# Initialize KiteConnect for each account
for i, account in enumerate(accounts):
    kite_instance = initialize_kite_for_account(account, verbose=is_first_run)
    if kite_instance:
        # Add kite instance to the account dictionary
        account['kite'] = kite_instance
        if is_first_run:
            print(f"✓ KiteConnect instance added to account {i+1}")
    else:
        account['kite'] = None
        if is_first_run:
            print(f"✗ KiteConnect instance not available for account {i+1}")

# Print connection summary for all accounts
print("\n" + "="*80)
print("KITECONNECT CONNECTION SUMMARY")
print("="*80)
initialized_count = sum(1 for acc in accounts if acc.get('kite') is not None)
print(f"Total accounts: {len(accounts)}")
print(f"Connected: {initialized_count}")
print(f"Not Connected: {len(accounts) - initialized_count}")

for i, account in enumerate(accounts, 1):
    account_name = account.get('account_holder_name', 'Unknown')
    account_kite_id = account.get('account_kite_id', 'Unknown')
    account_status = get_account_status(account)
    connection_status = "Connected" if account.get('kite') else "Not Connected"
    print(f"  Account {i}: {account_name} ({account_kite_id}) - [{account_status}] - {connection_status}")
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
    account_name = account.get('account_holder_name', 'Unknown')
    account_kite_id = account.get('account_kite_id', 'Unknown')
    account_status = get_account_status(account)
    
    print(f"\n{'─'*80}")
    print(f"POSITIONS FOR: {account_name} ({account_kite_id}) - [{account_status}]")
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
    
    # Filter positions to only show NFO or BFO exchanges
    all_positions = [pos for pos in net_positions if pos.get('exchange', '').upper() in ['NFO', 'BFO']]
    
    if not all_positions:
        print("  ✓ No positions in NFO/BFO exchanges")
        return
    
    open_positions = [pos for pos in all_positions if pos.get('quantity', 0) != 0]
    closed_positions = [pos for pos in all_positions if pos.get('quantity', 0) == 0]
    
    print(f"\n  Total Positions: {len(all_positions)} (Open: {len(open_positions)}, Closed: {len(closed_positions)})")
    print(
        f"\n  {'Status':<8} {'Symbol':<20} {'Exchange':<10} {'Product':<10} "
        f"{'Quantity':<12} {'Avg Price':<12} {'LTP':<12} {'P&L':<15}"
    )
    print(f"  {'-'*8} {'-'*20} {'-'*10} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*15}")
    
    total_api_pnl = 0
    total_cmp_pnl = 0
    for pos in all_positions:
        symbol = pos.get('tradingsymbol', 'N/A')
        exchange = pos.get('exchange', 'N/A')
        product = pos.get('product', 'N/A')
        quantity = pos.get('quantity', 0)
        avg_price = pos.get('average_price', 0)

        # Fetch fresh LTP and compute fallback P&L locally
        ltp, computed_pnl = _compute_ltp_and_pnl(account.get('kite'), pos)
        # Prefer API-provided P&L if present (already accounts for multipliers); otherwise use computed fallback
        api_pnl = pos.get('pnl', None)
        api_pnl_val = api_pnl if api_pnl is not None else 0
        cmp_pnl_val = computed_pnl if computed_pnl is not None else 0
        total_api_pnl += api_pnl_val
        total_cmp_pnl += cmp_pnl_val

        # Format values
        qty_str = f"{quantity:+.0f}" if quantity != 0 else "0"
        avg_price_str = f"{avg_price:.2f}" if avg_price else "0.00"
        ltp_str = f"{ltp:.2f}" if ltp else "0.00"

        # Prepare API and computed P&L strings
        api_str = f"API ₹{api_pnl_val:+,.2f}"
        cmp_str = f"CMP ₹{cmp_pnl_val:+,.2f}"

        pnl_display_api = api_str
        pnl_display_cmp = cmp_str

        status = "OPEN" if quantity != 0 else "CLOSED"
        print(f"  {status:<8} {symbol:<20} {exchange:<10} {product:<10} {qty_str:<12} {avg_price_str:<12} {ltp_str:<12} {pnl_display_api:<18} {pnl_display_cmp:<18}")
    
    # Print totals for API and Computed P&L
    total_api_str = f"API Total: ₹{total_api_pnl:+,.2f}"
    total_cmp_str = f"CMP Total: ₹{total_cmp_pnl:+,.2f}"
    print()
    # align totals under their columns
    print(f"  {'':<8} {'':<20} {'':<10} {'':<10} {'':<12} {'':<12} {'':<12} {total_api_str:<18} {total_cmp_str:<18}")
    print(f"{'─'*80}")


# Fetch and print positions for each account
for i, account in enumerate(accounts, 1):
    account_name = account.get('account_holder_name', 'Unknown')
    kite = account.get('kite')
    
    if not kite:
        account_status = get_account_status(account)
        account_kite_id = account.get('account_kite_id', 'Unknown')
        print(f"\n{'─'*80}")
        print(f"POSITIONS FOR: {account_name} ({account_kite_id}) - [{account_status}]")
        print(f"{'─'*80}")
        print("  ✗ Cannot fetch positions - KiteConnect not initialized")
        print(f"{'─'*80}")
        continue
    
    try:
        positions = get_positions_for_account(account)
        print_positions_for_account(account, positions)
    except Exception as e:
        account_status = get_account_status(account)
        account_kite_id = account.get('account_kite_id', 'Unknown')
        print(f"\n{'─'*80}")
        print(f"POSITIONS FOR: {account_name} ({account_kite_id}) - [{account_status}]")
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


def print_margins_for_account(account, margins, base_total_margin=None):
    account_name = account.get('account_holder_name', 'Unknown')
    account_kite_id = account.get("account_kite_id", "Unknown")
    account_status = get_account_status(account)

    print(f"\n{'─'*80}")
    print(f"MARGINS FOR: {account_name} ({account_kite_id}) - [{account_status}]")
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
    
    # Calculate and print ratio if base margin is provided
    if base_total_margin and base_total_margin > 0 and total is not None:
        ratio = total / base_total_margin
        print(f"  Ratio            : {ratio:.2f}")
    else:
        print(f"  Ratio            : N/A")

    print(f"{'─'*80}")


# Get base account's total margin for ratio calculation
base_total_margin_for_ratio = None
for acc in accounts:
    if acc.get('is_base_account') and acc.get('kite'):
        base_margins = get_margins_for_account(acc)
        if base_margins:
            equity = base_margins.get('equity', {})
            base_available = _safe_float(equity.get('net'))
            base_used = _safe_float(equity.get('utilised', {}).get('debits'))
            if base_available is not None and base_used is not None:
                base_total_margin_for_ratio = base_available + base_used
        break

for account in accounts:
    if not account.get("kite"):
        account_name = account.get('account_holder_name', 'Unknown')
        account_kite_id = account.get('account_kite_id', 'Unknown')
        account_status = get_account_status(account)
        print(f"\n{'─'*80}")
        print(f"MARGINS FOR: {account_name} ({account_kite_id}) - [{account_status}]")
        print(f"{'─'*80}")
        print("  ✗ Cannot fetch margins - KiteConnect not initialized")
        print(f"{'─'*80}")
        continue

    margins = get_margins_for_account(account)
    print_margins_for_account(account, margins, base_total_margin_for_ratio)

print("\n" + "="*80)
print("MARGINS FETCH COMPLETE")
print("="*80)


# Load lot sizes from config file (silently)
try:
    with open("lot_sizes_config.json", "r") as f:
        lot_sizes_config = json.load(f)
    lot_sizes = lot_sizes_config.get("lot_sizes", {})
except Exception as e:
    lot_sizes = {"NFO": 65, "BFO": 20}

NFO_LOT_SIZE = lot_sizes.get("NFO", 65)
BFO_LOT_SIZE = lot_sizes.get("BFO", 20)


# Position Mimicking Logic
# Position mimicking is now handled by sync_operations.py when trigger is activated
# The code below is kept for reference but not executed in main.py

def round_to_lot_size(quantity, exchange):
    """
    Round quantity UP to next multiple of lot size for the exchange.
    
    Args:
        quantity: The quantity to round
        exchange: 'NFO' or 'BFO'
    
    Returns:
        int: Quantity rounded UP to next lot size multiple
    """
    lot_size = NFO_LOT_SIZE if exchange.upper() == "NFO" else BFO_LOT_SIZE
    if lot_size <= 0:
        return 0
    if quantity <= 0:
        return 0
    # Round UP to next multiple (ceiling)
    rounded = math.ceil(quantity / lot_size) * lot_size
    return int(rounded)


def get_base_account_positions(base_account):
    """
    Get open NFO/BFO positions from base account.
    
    Args:
        base_account: Dictionary containing base account details with kite instance
    
    Returns:
        list: List of open positions (NFO/BFO only)
    """
    kite = base_account.get('kite')
    if not kite:
        return []
    
    try:
        positions = kite.positions()
        net_positions = positions.get('net', [])
        
        # Filter for open NFO/BFO positions only
        open_positions = [
            pos for pos in net_positions
            if pos.get('quantity', 0) != 0
            and pos.get('exchange', '').upper() in ['NFO', 'BFO']
        ]
        
        return open_positions
    except Exception as e:
        print(f"✗ Error fetching base account positions: {e}")
        return []


def get_total_margin(account):
    """
    Get total margin for an account.
    
    Args:
        account: Dictionary containing account details with kite instance
    
    Returns:
        float: Total margin (available + used) or None if error
    """
    kite = account.get('kite')
    if not kite:
        return None
    
    try:
        margins = kite.margins()
        equity = margins.get('equity', {})
        available = _safe_float(equity.get('net'))
        used = _safe_float(equity.get('utilised', {}).get('debits'))
        
        if available is not None and used is not None:
            return available + used
        return None
    except Exception as e:
        print(f"✗ Error fetching margin for {account.get('account_holder_name', 'Unknown')}: {e}")
        return None


def get_current_position_quantity(kite, symbol, exchange):
    """
    Get current position quantity for a symbol in an account.
    
    Args:
        kite: KiteConnect instance
        symbol: Trading symbol
        exchange: Exchange (NFO/BFO)
    
    Returns:
        int: Current quantity (0 if no position)
    """
    try:
        positions = kite.positions()
        net_positions = positions.get('net', [])
        
        for pos in net_positions:
            if (pos.get('tradingsymbol', '').upper() == symbol.upper() and 
                pos.get('exchange', '').upper() == exchange.upper()):
                return pos.get('quantity', 0)
        return 0
    except Exception as e:
        print(f"  ⚠️  Error fetching current position for {symbol}: {e}")
        return 0


def mimic_position_in_account(base_position, target_account, base_total_margin, target_total_margin):
    """
    Mimic a position from base account to target account with proportional quantity.
    Only trades the delta needed to achieve the intended proportional position.
    
    Args:
        base_position: Position dictionary from base account
        target_account: Target account dictionary with kite instance
        base_total_margin: Total margin of base account
        target_total_margin: Total margin of target account
    
    Returns:
        bool: True if order placed successfully or no action needed, False otherwise
    """
    # Safety check: Only trade if Copy Trades is set to "YES"
    copy_trades = str(target_account.get('copy_trades', '')).strip().upper()
    if copy_trades != 'YES':
        print(f"  ⚠️  Skipping: Copy Trades is not set to 'YES' for this account")
        return False
    
    kite = target_account.get('kite')
    if not kite:
        return False
    
    symbol = base_position.get('tradingsymbol', '')
    exchange = base_position.get('exchange', '').upper()
    base_quantity = base_position.get('quantity', 0)
    
    if not symbol or not exchange or base_quantity == 0:
        return False
    
    # Calculate intended proportional quantity
    if base_total_margin and base_total_margin > 0:
        intended_proportional_qty = (target_total_margin / base_total_margin) * abs(base_quantity)
    else:
        intended_proportional_qty = 0
    
    # Round intended quantity to lot size (always round up)
    intended_qty = round_to_lot_size(intended_proportional_qty, exchange)
    
    if intended_qty == 0:
        print(f"  ⚠️  Skipping {symbol}: Intended quantity is 0 after rounding to lot size")
        return False
    
    # Get current position quantity in target account
    current_qty = get_current_position_quantity(kite, symbol, exchange)
    
    # Calculate delta (difference between intended and current)
    # Preserve the sign from base position
    base_sign = 1 if base_quantity >= 0 else -1
    intended_qty_signed = intended_qty * base_sign
    delta_qty = intended_qty_signed - current_qty
    
    print(f"  {symbol} ({exchange}):")
    print(f"    Base quantity: {base_quantity}")
    print(f"    Intended proportional quantity: {intended_qty_signed}")
    print(f"    Current quantity in target: {current_qty}")
    print(f"    Delta needed: {delta_qty}")
    
    # If delta is 0 or very small (within lot size), no trade needed
    lot_size = NFO_LOT_SIZE if exchange == "NFO" else BFO_LOT_SIZE
    if abs(delta_qty) < lot_size:
        print(f"    ✓ Already at target position (delta < lot size). No trade needed.")
        return True
    
    # Round delta to lot size
    delta_qty_rounded = round_to_lot_size(abs(delta_qty), exchange)
    if delta_qty < 0:
        delta_qty_rounded = -delta_qty_rounded
    
    if delta_qty_rounded == 0:
        print(f"    ✓ Already at target position. No trade needed.")
        return True
    
    # Determine transaction type based on delta
    if delta_qty_rounded > 0:
        transaction_type = "BUY"
        order_qty = abs(delta_qty_rounded)
    else:
        transaction_type = "SELL"
        order_qty = abs(delta_qty_rounded)
    
    # Get current market price (LTP) - use from base position or fetch
    ltp = base_position.get('last_price', 0)
    if ltp <= 0:
        try:
            # Try to fetch LTP using exchange:symbol format
            quote_key = f"{exchange}:{symbol}"
            quote_data = kite.quote([quote_key])
            if quote_data and quote_key in quote_data:
                ltp = quote_data[quote_key].get('last_price', 0)
        except Exception as e:
            print(f"  ⚠️  Could not fetch LTP for {symbol}: {e}")
    
    if ltp <= 0:
        print(f"    ✗ Cannot place order: Invalid LTP")
        return False
    
    # Place order for delta quantity only
    try:
        order_result = kite.place_order(
            variety="regular",
            exchange=exchange,
            tradingsymbol=symbol,
            transaction_type=transaction_type,
            order_type="MARKET",  # Using MARKET order for immediate execution
            quantity=order_qty,
            product="NRML",
            validity="DAY"
        )
        
        print(f"    ✓ Order placed: {transaction_type} {order_qty} @ MARKET (delta trade)")
        print(f"      Order ID: {order_result}")
        return True
    except Exception as e:
        print(f"    ✗ Failed to place order: {e}")
        return False


# Position mimicking execution removed - now handled by sync_operations.py on trigger
# The functions (round_to_lot_size, get_base_account_positions, mimic_position_in_account, etc.)
# are kept above for reference but are not executed here

def get_account_sync_status(account):
    """
    Get the sync status for an account.
    
    Returns:
        str: "BASE", "SYNCED", or "NOT SYNCED"
    """
    if account.get('is_base_account'):
        return "BASE"
    elif str(account.get('copy_trades', '')).strip().upper() == 'YES':
        return "SYNCED"
    else:
        return "NOT SYNCED"


def print_positions_after_sync(account, positions):
    """
    Print positions with account sync status.
    
    Args:
        account: Dictionary containing account details
        positions: Positions data from KiteConnect API
    """
    account_name = display_account_name(account)
    account_kite_id = account.get('account_kite_id', 'Unknown')
    sync_status = get_account_sync_status(account)
    
    print(f"\n{'─'*80}")
    print(f"POSITIONS FOR: {account_name} ({account_kite_id}) - [{sync_status}]")
    print(f"{'─'*80}")
    
    if not positions:
        print("  No positions data available")
        return
    
    # KiteConnect positions API returns a dict with 'net' and 'day' keys
    net_positions = positions.get('net', [])
    
    if not net_positions:
        print("  ✓ No positions")
        return
    
    # Filter positions to only show NFO or BFO exchanges
    all_positions = [pos for pos in net_positions if pos.get('exchange', '').upper() in ['NFO', 'BFO']]
    
    if not all_positions:
        print("  ✓ No positions in NFO/BFO exchanges")
        return
    
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

        # Fetch fresh LTP and compute P&L locally
        ltp, pnl = _compute_ltp_and_pnl(account.get('kite'), pos)
        total_pnl += pnl

        # Format values
        qty_str = f"{quantity:+.0f}" if quantity != 0 else "0"
        avg_price_str = f"{avg_price:.2f}" if avg_price else "0.00"
        ltp_str = f"{ltp:.2f}" if ltp else "0.00"

        # Prepare API and computed P&L strings
        api_pnl_val = api_pnl
        cmp_pnl_val = computed_pnl
        api_str = f"API ₹{api_pnl_val:+,.2f}" if api_pnl_val is not None else "API N/A"
        cmp_str = f"CMP ₹{cmp_pnl_val:+,.2f}"

        # Combine into display string
        pnl_display = f"{api_str} / {cmp_str}"

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


# Post-sync position display removed - now handled by sync_operations.py after trigger






