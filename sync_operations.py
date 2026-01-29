#!/usr/bin/env python3
"""
Sync operations module - called on each trigger.
Contains only the sync logic and position printing (no verbose initialization).
"""
import json
import datetime
import os
import sys
import math
import time
import urllib.parse
from kiteconnect import KiteConnect, KiteTicker
# Accounts are now loaded from local config file (accounts_config.json)
# No need to import get_all_accounts_from_google_sheet

# Import shared functions from main_copy
# We'll need to import or redefine the necessary functions
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _safe_float(val):
    try:
        return float(val)
    except Exception:
        return None


def display_account_name(account: dict) -> str:
    name = account.get("account_holder_name", "Unknown")
    return f"BASE ACCOUNT {name}" if account.get("is_base_account") else name


def initialize_kite_quiet(account):
    """Quick, quiet initialization of KiteConnect (no verbose output)."""
    account_kite_id = account.get('account_kite_id', 'Unknown')
    api_key = account.get('api_key')
    api_secret = account.get('api_secret')
    
    if not api_key or not api_secret:
        return None
    
    try:
        kite = KiteConnect(api_key=api_key)
        access_token_file = f"AccessToken/{account_kite_id}_{datetime.datetime.now().date()}.json"
        
        if os.path.exists(access_token_file):
            with open(access_token_file, "r") as f:
                access_token = json.load(f)
            kite.set_access_token(access_token)
            return kite
        else:
            # Try to get from request URL if available
            request_url = account.get('request_url_by_zerodha')
            if request_url and request_url != 'None' and 'request_token=' in request_url:
                try:
                    parsed_url = urllib.parse.urlparse(request_url)
                    params = urllib.parse.parse_qs(parsed_url.query)
                    if 'request_token' in params:
                        request_token = params['request_token'][0]
                        access_token = kite.generate_session(
                            request_token=request_token,
                            api_secret=api_secret
                        )['access_token']
                        os.makedirs("AccessToken", exist_ok=True)
                        with open(access_token_file, "w") as f:
                            json.dump(access_token, f)
                        kite.set_access_token(access_token)
                        return kite
                except:
                    pass
        return None
    except:
        return None


def get_base_account_positions(base_account):
    """Get open NFO/BFO positions from base account."""
    kite = base_account.get('kite')
    if not kite:
        return []
    
    try:
        positions = kite.positions()
        net_positions = positions.get('net', [])
        open_positions = [
            pos for pos in net_positions
            if pos.get('quantity', 0) != 0
            and pos.get('exchange', '').upper() in ['NFO', 'BFO']
        ]
        return open_positions
    except Exception as e:
        print(f"✗ Error fetching base account positions: {e}")
        return []


def get_target_account_open_positions(target_account):
    """Get open NFO/BFO positions from target account."""
    kite = target_account.get('kite')
    if not kite:
        return []
    
    try:
        positions = kite.positions()
        net_positions = positions.get('net', [])
        open_positions = [
            pos for pos in net_positions
            if pos.get('quantity', 0) != 0
            and pos.get('exchange', '').upper() in ['NFO', 'BFO']
        ]
        return open_positions
    except Exception as e:
        print(f"✗ Error fetching target account positions: {e}")
        return []


def close_position_in_account(position, target_account):
    """Close a position in target account (sell if long, buy if short)."""
    kite = target_account.get('kite')
    if not kite:
        return False
    
    symbol = position.get('tradingsymbol', '')
    exchange = position.get('exchange', '').upper()
    current_qty = position.get('quantity', 0)
    
    if not symbol or not exchange or current_qty == 0:
        return False
    
    # Determine transaction type: if quantity is positive (long), we need to SELL to close
    # If quantity is negative (short), we need to BUY to close
    if current_qty > 0:
        transaction_type = "SELL"
        order_qty = abs(current_qty)
    else:
        transaction_type = "BUY"
        order_qty = abs(current_qty)
    
    # Round to lot size
    order_qty_rounded = round_to_lot_size(order_qty, exchange)
    if order_qty_rounded == 0:
        print(f"    ✓ Position already closed or too small to trade")
        return True
    
    # Get LTP
    ltp = position.get('last_price', 0)
    if ltp <= 0:
        try:
            quote_key = f"{exchange}:{symbol}"
            quote_data = kite.quote([quote_key])
            if quote_data and quote_key in quote_data:
                ltp = quote_data[quote_key].get('last_price', 0)
        except:
            pass
    
    if ltp <= 0:
        print(f"    ✗ Cannot close position: Invalid LTP")
        return False
    
    # Place order(s) to close position (recursive split if qty > max_quantity)
    try:
        ok, order_ids, order_errors = _place_market_order_recursive(
            kite, exchange, symbol, transaction_type, order_qty_rounded,
            product="NRML", validity="DAY", tag_prefix="close",
        )
        if not ok or not order_ids:
            print(f"    ✗ Failed to place order to close")
            return False
        n = len(order_ids)
        suffix = f" ({n} orders)" if n > 1 else ""
        print(f"    ✓ Order placed to close: {transaction_type} {order_qty_rounded} @ MARKET{suffix}")
        print(f"      Order ID(s): {', '.join(str(oid) for oid in order_ids)}")
        
        # Check for order errors (from immediate place_order response)
        if order_errors:
            print(f"    ⚠️  Order Execution Errors:")
            for oid, error_msg in order_errors:
                print(f"      ✗ Order ID {oid}: {error_msg}")
            return False
        return True
    except Exception as e:
        print(f"    ✗ Failed to close position: {e}")
        return False


def get_total_margin(account):
    """Get total margin for an account."""
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
        return None


# Load lot sizes and max quantity
try:
    with open("lot_sizes_config.json", "r") as f:
        lot_sizes_config = json.load(f)
    lot_sizes = lot_sizes_config.get("lot_sizes", {})
    max_quantity = lot_sizes_config.get("max_quantity", {})
except:
    lot_sizes = {"NFO": 65, "BFO": 20}
    max_quantity = {"NFO": 1755, "BFO": 2000}

NFO_LOT_SIZE = lot_sizes.get("NFO", 65)
BFO_LOT_SIZE = lot_sizes.get("BFO", 20)
NFO_MAX_QUANTITY = max_quantity.get("NFO", 1755)
BFO_MAX_QUANTITY = max_quantity.get("BFO", 2000)


def _get_max_quantity(exchange):
    return NFO_MAX_QUANTITY if exchange.upper() == "NFO" else BFO_MAX_QUANTITY


def _place_market_order_recursive(kite, exchange, symbol, transaction_type, order_qty,
                                  product="NRML", validity="DAY",
                                  tag_prefix="", slice_index=1, order_ids=None, order_errors=None):
    """
    Place MARKET order(s). If order_qty > max_quantity for exchange, split recursively.
    order_qty must be a multiple of lot size.
    Returns (success: bool, list of order_ids, list of errors). Modifies order_ids and order_errors in place when recursing.
    """
    if order_ids is None:
        order_ids = []
    if order_errors is None:
        order_errors = []
    max_qty = _get_max_quantity(exchange)
    if order_qty <= 0:
        return True, order_ids, order_errors
    if order_qty <= max_qty:
        tag = f"{tag_prefix}{slice_index}".strip() or None
        try:
            oid = kite.place_order(
                variety="regular",
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                order_type="MARKET",
                quantity=order_qty,
                product=product,
                validity=validity,
                tag=tag[:20] if tag else None,
            )
            order_ids.append(oid)
            return True, order_ids, order_errors
        except Exception as e:
            # Re-raise with more context
            raise Exception(f"Failed to place order for {symbol} ({exchange}): {str(e)}")
    # Split: place max_qty first, then remainder
    tag = f"{tag_prefix}{slice_index}".strip() or None
    try:
        oid1 = kite.place_order(
            variety="regular",
            exchange=exchange,
            tradingsymbol=symbol,
            transaction_type=transaction_type,
            order_type="MARKET",
            quantity=max_qty,
            product=product,
            validity=validity,
            tag=tag[:20] if tag else None,
        )
        order_ids.append(oid1)
    except Exception as e:
        raise Exception(f"Failed to place order for {symbol} ({exchange}), qty {max_qty}: {str(e)}")
    ok, _, _ = _place_market_order_recursive(
        kite, exchange, symbol, transaction_type, order_qty - max_qty,
        product=product, validity=validity, tag_prefix=tag_prefix, slice_index=slice_index + 1,
        order_ids=order_ids, order_errors=order_errors,
    )
    return ok, order_ids, order_errors


def round_to_lot_size(quantity, exchange):
    """Round quantity UP to next multiple of lot size."""
    lot_size = NFO_LOT_SIZE if exchange.upper() == "NFO" else BFO_LOT_SIZE
    if lot_size <= 0:
        return 0
    if quantity <= 0:
        return 0
    rounded = math.ceil(quantity / lot_size) * lot_size
    return int(rounded)


def get_current_position_quantity(kite, symbol, exchange):
    """Get current position quantity for a symbol."""
    try:
        positions = kite.positions()
        net_positions = positions.get('net', [])
        
        for pos in net_positions:
            if (pos.get('tradingsymbol', '').upper() == symbol.upper() and 
                pos.get('exchange', '').upper() == exchange.upper()):
                return pos.get('quantity', 0)
        return 0
    except:
        return 0


def mimic_position_in_account(base_position, target_account, base_total_margin, target_total_margin):
    """Mimic position with delta trading."""
    copy_trades = str(target_account.get('copy_trades', '')).strip().upper()
    if copy_trades != 'YES':
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
    
    intended_qty = round_to_lot_size(intended_proportional_qty, exchange)
    if intended_qty == 0:
        return False
    
    # Get current position
    current_qty = get_current_position_quantity(kite, symbol, exchange)
    
    # Calculate delta
    base_sign = 1 if base_quantity >= 0 else -1
    intended_qty_signed = intended_qty * base_sign
    delta_qty = intended_qty_signed - current_qty
    
    print(f"  {symbol} ({exchange}):")
    print(f"    Base quantity: {base_quantity}")
    print(f"    Intended proportional quantity: {intended_qty_signed}")
    print(f"    Current quantity in target: {current_qty}")
    print(f"    Delta needed: {delta_qty}")
    
    # Check if trade needed
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
    
    # Determine transaction type
    if delta_qty_rounded > 0:
        transaction_type = "BUY"
        order_qty = abs(delta_qty_rounded)
    else:
        transaction_type = "SELL"
        order_qty = abs(delta_qty_rounded)
    
    # Get LTP
    ltp = base_position.get('last_price', 0)
    if ltp <= 0:
        try:
            quote_key = f"{exchange}:{symbol}"
            quote_data = kite.quote([quote_key])
            if quote_data and quote_key in quote_data:
                ltp = quote_data[quote_key].get('last_price', 0)
        except:
            pass
    
    if ltp <= 0:
        print(f"    ✗ Cannot place order: Invalid LTP")
        return False
    
    # Place order(s) (recursive split if qty > max_quantity)
    try:
        ok, order_ids, order_errors = _place_market_order_recursive(
            kite, exchange, symbol, transaction_type, order_qty,
            product="NRML", validity="DAY", tag_prefix="mimic",
        )
        if not ok or not order_ids:
            print(f"    ✗ Failed to place order")
            return False
        n = len(order_ids)
        suffix = f" ({n} orders)" if n > 1 else ""
        print(f"    ✓ Order placed: {transaction_type} {order_qty} @ MARKET{suffix} (delta trade)")
        print(f"      Order ID(s): {', '.join(str(oid) for oid in order_ids)}")
        
        # Check for order errors (from immediate place_order response)
        if order_errors:
            print(f"    ⚠️  Order Execution Errors:")
            for oid, error_msg in order_errors:
                print(f"      ✗ Order ID {oid}: {error_msg}")
            return False
        return True
    except Exception as e:
        print(f"    ✗ Failed to place order: {e}")
        return False


def get_positions_for_account(account):
    """Fetch positions for an account."""
    kite = account.get('kite')
    if not kite:
        return None
    
    try:
        return kite.positions()
    except:
        return None


def get_account_sync_status(account):
    """Get sync status for an account."""
    copy_trades = str(account.get('copy_trades', '')).strip().upper()
    if copy_trades == 'BASE' or account.get('is_base_account'):
        return "BASE"
    elif copy_trades == 'YES':
        return "SYNCED"
    else:
        return "NOT SYNCED"


def print_positions_after_sync(account, positions):
    """Print positions with account sync status."""
    account_name = display_account_name(account)
    account_kite_id = account.get('account_kite_id', 'Unknown')
    sync_status = get_account_sync_status(account)
    kite = account.get('kite')
    
    print(f"\n{'─'*80}")
    print(f"POSITIONS FOR: {account_name} ({account_kite_id}) - [{sync_status}]")
    print(f"{'─'*80}")
    
    if not positions:
        print("  No positions data available")
        return
    
    net_positions = positions.get('net', [])
    if not net_positions:
        print("  ✓ No positions")
        return
    
    # Filter for NFO/BFO only
    all_positions = [pos for pos in net_positions if pos.get('exchange', '').upper() in ['NFO', 'BFO']]
    
    if not all_positions:
        print("  ✓ No positions in NFO/BFO exchanges")
        return
    
    open_positions = [pos for pos in all_positions if pos.get('quantity', 0) != 0]
    closed_positions = [pos for pos in all_positions if pos.get('quantity', 0) == 0]
    
    print(f"\n  Total Positions: {len(all_positions)} (Open: {len(open_positions)}, Closed: {len(closed_positions)})")
    print(
        f"\n  {'Status':<8} {'Symbol':<20} {'Exchange':<10} {'Product':<10} "
        f"{'Quantity':<12} {'Avg Price':<12} {'LTP':<12} {'P&L API':<18} {'P&L CMP':<18}"
    )
    print(f"  {'-'*8} {'-'*20} {'-'*10} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*18} {'-'*18}")
    
    total_api_pnl = 0
    total_cmp_pnl = 0
    for pos in all_positions:
        symbol = pos.get('tradingsymbol', 'N/A')
        exchange = pos.get('exchange', 'N/A')
        product = pos.get('product', 'N/A')
        quantity = pos.get('quantity', 0)
        avg_price = pos.get('average_price', 0)

        # Fetch fresh LTP (fallback to position value)
        ltp = pos.get('last_price', 0) or 0
        try:
            if kite and symbol and exchange:
                quote_key = f"{exchange}:{symbol}"
                quote_data = kite.quote([quote_key])
                if quote_data and quote_key in quote_data:
                    ltp = quote_data[quote_key].get('last_price', ltp)
        except Exception:
            pass

        # Recompute fallback P&L locally: (LTP - Avg Price) * Quantity
        try:
            computed_pnl = (ltp - (avg_price or 0)) * (quantity or 0)
        except Exception:
            computed_pnl = 0
        # Prefer API-provided P&L if present
        api_pnl = pos.get('pnl', None)
        api_pnl_val = api_pnl if api_pnl is not None else 0
        cmp_pnl_val = computed_pnl if computed_pnl is not None else 0
        total_api_pnl += api_pnl_val
        total_cmp_pnl += cmp_pnl_val

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
    print(f"  {'':<8} {'':<20} {'':<10} {'':<10} {'':<12} {'':<12} {'':<12} {total_api_str:<18} {total_cmp_str:<18}")
    print(f"{'─'*80}")


def load_accounts_config():
    """Load account configuration from local file."""
    config_file = "accounts_config.json"
    if not os.path.exists(config_file):
        raise Exception(f"Account configuration file '{config_file}' not found. Please run main.py first to generate it.")
    
    with open(config_file, "r") as f:
        config = json.load(f)
    
    accounts = config.get("accounts", [])
    
    # Ensure is_base_account is set correctly
    base_account_found = False
    for account in accounts:
        copy_trades = str(account.get('copy_trades', '')).strip().upper()
        if copy_trades == 'BASE' or account.get('is_base_account'):
            account["is_base_account"] = True
            base_account_found = True
        else:
            account["is_base_account"] = False
    
    # If no account marked as "Base", default to first account
    if not base_account_found and accounts:
        accounts[0]["is_base_account"] = True
    
    return accounts


def run_sync_operations():
    """Main function to run sync operations (called on each trigger)."""
    print("\n" + "="*80)
    print(f"SYNC TRIGGERED AT: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Load accounts from local config file
    try:
        accounts = load_accounts_config()
    except Exception as e:
        print(f"✗ Failed to load accounts: {e}")
        return False
    
    # Quick, quiet initialization
    print("\nReinitializing connections (quiet mode)...")
    for account in accounts:
        account['kite'] = initialize_kite_quiet(account)
    
    # Get base account
    base_account = None
    for account in accounts:
        if account.get('is_base_account') and account.get('kite'):
            base_account = account
            break
    
    if not base_account:
        print("✗ Base account not found or KiteConnect not initialized")
        return False
    
    # Get base positions
    base_positions = get_base_account_positions(base_account)
    
    # Find target accounts
    target_accounts = [
        acc for acc in accounts
        if not acc.get('is_base_account')
        and acc.get('kite')
        and str(acc.get('copy_trades', '')).strip().upper() == 'YES'
    ]
    
    if not target_accounts:
        print("✓ No target accounts with 'Copy Trades' = 'YES'")
    else:
        print(f"✓ Found {len(target_accounts)} target account(s) for position syncing")
        
        if not base_positions:
            print("✓ No open NFO/BFO positions in base account - closing all positions in synced accounts")
        else:
            print(f"✓ Found {len(base_positions)} open NFO/BFO position(s) in base account")
        
        # Get base total margin (needed for proportional calculations)
        base_total_margin = get_total_margin(base_account)
        if base_total_margin and base_total_margin > 0:
            print(f"✓ Base account total margin: ₹{base_total_margin/1e7:.4f} Cr")
        elif base_positions:
            print("⚠️  Warning: Base account total margin is invalid - cannot calculate proportional quantities")
        
        # Process each target account
        for target_account in target_accounts:
            target_name = display_account_name(target_account)
            print(f"\n{'─'*80}")
            print(f"SYNCING POSITIONS IN: {target_name}")
            print(f"{'─'*80}")
            
            target_total_margin = get_total_margin(target_account)
            if not target_total_margin or target_total_margin <= 0:
                print(f"  ✗ Cannot sync: Invalid total margin")
                continue
            
            print(f"  Target total margin: ₹{target_total_margin/1e7:.4f} Cr")
            if base_total_margin and base_total_margin > 0:
                print(f"  Proportionality ratio: {target_total_margin/base_total_margin:.4f}")
            
            # Step 1: Close positions that exist in target but NOT in base account
            target_open_positions = get_target_account_open_positions(target_account)
            
            # Create a set of base position keys (symbol+exchange) for quick lookup
            base_position_keys = set()
            for base_pos in base_positions:
                symbol = base_pos.get('tradingsymbol', '').upper()
                exchange = base_pos.get('exchange', '').upper()
                if symbol and exchange:
                    base_position_keys.add(f"{exchange}:{symbol}")
            
            # Find positions to close (in target but not in base)
            # If base has no positions, close ALL positions in target
            positions_to_close = []
            for target_pos in target_open_positions:
                symbol = target_pos.get('tradingsymbol', '').upper()
                exchange = target_pos.get('exchange', '').upper()
                if symbol and exchange:
                    pos_key = f"{exchange}:{symbol}"
                    # Close if base has no positions OR if this position is not in base
                    if not base_positions or pos_key not in base_position_keys:
                        positions_to_close.append(target_pos)
            
            if positions_to_close:
                print(f"\n  Closing {len(positions_to_close)} position(s) not in base account:")
                closed_count = 0
                for pos_to_close in positions_to_close:
                    symbol = pos_to_close.get('tradingsymbol', 'N/A')
                    exchange = pos_to_close.get('exchange', 'N/A')
                    qty = pos_to_close.get('quantity', 0)
                    print(f"\n  Closing: {symbol} ({exchange}) - Current quantity: {qty}")
                    if close_position_in_account(pos_to_close, target_account):
                        closed_count += 1
                print(f"\n  ✓ Closed {closed_count}/{len(positions_to_close)} positions")
            # else: no positions to close (silent)
            
            # Step 2: Sync positions that exist in base account (add/update)
            if base_positions and base_total_margin and base_total_margin > 0:
                print(f"\n  Syncing {len(base_positions)} position(s) from base account:")
                success_count = 0
                for base_pos in base_positions:
                    symbol = base_pos.get('tradingsymbol', 'N/A')
                    exchange = base_pos.get('exchange', 'N/A')
                    base_qty = base_pos.get('quantity', 0)
                    
                    print(f"\n  Syncing: {symbol} ({exchange})")
                    print(f"    Base quantity: {base_qty}")
                    
                    if mimic_position_in_account(base_pos, target_account, base_total_margin, target_total_margin):
                        success_count += 1
                
                print(f"\n  ✓ Successfully processed {success_count}/{len(base_positions)} positions")
            elif base_positions:
                print(f"\n  ⚠️  Cannot sync positions: Base account total margin is invalid")
            
            print(f"{'─'*80}")
    
    # Print updated positions
    print("\n" + "="*80)
    print("UPDATED POSITIONS AFTER SYNC")
    print("="*80)
    
    for account in accounts:
        if not account.get('kite'):
            sync_status = get_account_sync_status(account)
            print(f"\n{'─'*80}")
            print(f"POSITIONS FOR: {display_account_name(account)} - [{sync_status}]")
            print(f"{'─'*80}")
            print("  ✗ Cannot fetch positions - KiteConnect not initialized")
            print(f"{'─'*80}")
            continue
        
        try:
            positions = get_positions_for_account(account)
            print_positions_after_sync(account, positions)
        except Exception as e:
            sync_status = get_account_sync_status(account)
            print(f"\n{'─'*80}")
            print(f"POSITIONS FOR: {display_account_name(account)} - [{sync_status}]")
            print(f"{'─'*80}")
            print(f"  ✗ Error: {e}")
            print(f"{'─'*80}")
    
    print("\n" + "="*80)
    print("SYNC OPERATIONS COMPLETE")
    print("="*80)
    
    return True


def check_order_by_id(order_id):
    """Utility function to check a specific order ID across all accounts."""
    print(f"\n{'='*80}")
    print(f"CHECKING ORDER STATUS: {order_id}")
    print(f"{'='*80}")
    
    # Load accounts from local config file
    try:
        accounts = load_accounts_config()
    except Exception as e:
        print(f"Error loading accounts: {e}")
        return
    
    # Check order in each account
    for account in accounts:
        kite = initialize_kite_quiet(account)
        if not kite:
            continue
        
        try:
            order_history = kite.order_history(order_id)
            if order_history:
                account_name = account.get('account_holder_name', 'Unknown')
                account_kite_id = account.get('account_kite_id', 'Unknown')
                
                print(f"\n✓ Found in account: {account_name} ({account_kite_id})")
                print("-"*80)
                
                for order in order_history:
                    print(f"Order ID: {order.get('order_id')}")
                    print(f"Exchange Order ID: {order.get('exchange_order_id')}")
                    print(f"Status: {order.get('status')}")
                    print(f"Status Message: {order.get('status_message')}")
                    print(f"Status Message Raw: {order.get('status_message_raw')}")
                    print(f"Trading Symbol: {order.get('tradingsymbol')}")
                    print(f"Exchange: {order.get('exchange')}")
                    print(f"Transaction Type: {order.get('transaction_type')}")
                    print(f"Order Type: {order.get('order_type')}")
                    print(f"Quantity: {order.get('quantity')}")
                    print(f"Filled Quantity: {order.get('filled_quantity')}")
                    print(f"Pending Quantity: {order.get('pending_quantity')}")
                    print(f"Cancelled Quantity: {order.get('cancelled_quantity')}")
                    print(f"Price: {order.get('price')}")
                    print(f"Average Price: {order.get('average_price')}")
                    print(f"Order Timestamp: {order.get('order_timestamp')}")
                    print(f"Exchange Timestamp: {order.get('exchange_timestamp')}")
                    
                    status = order.get('status', '').upper()
                    if status in ['REJECTED', 'CANCELLED']:
                        print(f"\n⚠️  ORDER FAILED:")
                        print(f"   Status: {status}")
                        print(f"   Error: {order.get('status_message')}")
                        print(f"   Raw Error: {order.get('status_message_raw')}")
                    elif status == 'COMPLETE':
                        print(f"\n✓ ORDER COMPLETED")
                    else:
                        print(f"\n⏳ ORDER STATUS: {status} (in progress)")
                    
                    print("-"*80)
                return
        except Exception as e:
            # Order not found in this account
            continue
    
    print(f"\n✗ Order {order_id} not found in any account.")
    print("Order IDs are account-specific. Make sure you're checking the correct account.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--check-order":
        # Check specific order
        order_id = sys.argv[2] if len(sys.argv) > 2 else None
        if order_id:
            check_order_by_id(order_id)
        else:
            print("Usage: python sync_operations.py --check-order <order_id>")
    else:
        run_sync_operations()
