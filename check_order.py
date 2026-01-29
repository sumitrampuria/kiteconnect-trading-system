#!/usr/bin/env python3
"""
Quick script to check order status for a specific order ID.
Run this from the project directory with proper Python environment activated.
"""
import json
import datetime
import os
from kiteconnect import KiteConnect

def check_order(order_id, account_kite_id=None):
    """Check order status. If account_kite_id provided, only check that account."""
    print(f"Checking order: {order_id}")
    print("="*80)
    
    # If account_kite_id provided, check only that account
    if account_kite_id:
        accounts_to_check = [account_kite_id]
    else:
        # Check all accounts in AccessToken folder
        access_token_dir = "AccessToken"
        if not os.path.exists(access_token_dir):
            print("AccessToken folder not found")
            return
        
        accounts_to_check = set()
        for filename in os.listdir(access_token_dir):
            if filename.endswith('.json'):
                # Extract account ID from filename (format: ACCOUNTID_YYYY-MM-DD.json)
                account_id = filename.split('_')[0]
                accounts_to_check.add(account_id)
    
    # We need API keys - let's try to get from Google Sheets or check if we can query orders
    # For now, let's check if we can get orders from any account
    print("Note: To check order status, we need to query each account.")
    print("Order IDs are account-specific.")
    print(f"\nTo find the error, check:")
    print("1. Kite Connect app/website - Orders section")
    print("2. Order history in the account where the order was placed")
    print(f"\nOrder ID: {order_id}")
    print("This order ID is specific to one account.")
    
    # Try to load accounts and check
    try:
        from google_sheets_reader import get_all_accounts_from_google_sheet
        
        accounts = get_all_accounts_from_google_sheet(
            spreadsheet_id="1h9r9DyHgXX39EysPEzZDn70mBM7jQa-I1l8u6bl92M4",
            gid=736151233,
            header_row=7,
            data_start_row=8
        )
        
        for account in accounts:
            kite_id = account.get('account_kite_id', '')
            api_key = account.get('api_key')
            api_secret = account.get('api_secret')
            
            if not api_key or not api_secret:
                continue
            
            try:
                kite = KiteConnect(api_key=api_key)
                token_file = f"AccessToken/{kite_id}_{datetime.datetime.now().date()}.json"
                
                if os.path.exists(token_file):
                    with open(token_file, "r") as f:
                        access_token = json.load(f)
                    kite.set_access_token(access_token)
                    
                    # Try to get order history
                    try:
                        order_history = kite.order_history(order_id)
                        if order_history:
                            print(f"\n✓ Found order in account: {account.get('account_holder_name')} ({kite_id})")
                            print("-"*80)
                            for order in order_history:
                                print(f"Status: {order.get('status')}")
                                print(f"Status Message: {order.get('status_message')}")
                                print(f"Status Message Raw: {order.get('status_message_raw')}")
                                print(f"Trading Symbol: {order.get('tradingsymbol')}")
                                print(f"Exchange: {order.get('exchange')}")
                                print(f"Transaction Type: {order.get('transaction_type')}")
                                print(f"Quantity: {order.get('quantity')}")
                                print(f"Filled: {order.get('filled_quantity')}")
                                print(f"Pending: {order.get('pending_quantity')}")
                                print(f"Cancelled: {order.get('cancelled_quantity')}")
                                
                                if order.get('status') in ['REJECTED', 'CANCELLED']:
                                    print(f"\n⚠️  ERROR DETAILS:")
                                    print(f"   Status: {order.get('status')}")
                                    print(f"   Error: {order.get('status_message')}")
                                    print(f"   Raw Error: {order.get('status_message_raw')}")
                            return
                    except Exception as e:
                        # Order not found in this account
                        continue
            except Exception as e:
                continue
        
        print(f"\nOrder {order_id} not found in any account.")
        print("The order may have been placed in a different account or the order ID is incorrect.")
        
    except ImportError:
        print("Cannot import google_sheets_reader. Please run from project directory with dependencies installed.")

if __name__ == "__main__":
    import sys
    order_id = sys.argv[1] if len(sys.argv) > 1 else None
    account_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not order_id:
        print("Usage: python check_order.py <order_id> [account_kite_id]")
        sys.exit(1)
    
    check_order(order_id, account_id)
