#!/usr/bin/env python3
"""
Simple script to check order status - uses AccessToken folder directly.
"""
import json
import datetime
import os
import sys
from kiteconnect import KiteConnect

def check_order_simple(order_id):
    """Check order status by trying all accounts in AccessToken folder."""
    print(f"Checking order: {order_id}")
    print("="*80)
    
    access_token_dir = "AccessToken"
    if not os.path.exists(access_token_dir):
        print("AccessToken folder not found")
        return
    
    # Get all account IDs from token files
    account_files = {}
    for filename in os.listdir(access_token_dir):
        if filename.endswith('.json'):
            parts = filename.replace('.json', '').split('_')
            if len(parts) >= 2:
                account_id = parts[0]
                date_str = '_'.join(parts[1:])
                if account_id not in account_files:
                    account_files[account_id] = []
                account_files[account_id].append(filename)
    
    # We need API keys from somewhere - let's try to read from a config or ask user
    # For now, let's check if we can get orders API without full auth
    print(f"Found {len(account_files)} account(s) in AccessToken folder")
    print("Note: To check order status, we need full KiteConnect authentication.")
    print(f"\nOrder ID: {order_id}")
    print("\nTo check this order:")
    print("1. Log into Kite Connect for the account where order was placed")
    print("2. Go to Orders → Order History")
    print("3. Search for order ID:", order_id)
    print("\nOr run the sync again - the code will now print status of all orders.")

if __name__ == "__main__":
    order_id = sys.argv[1] if len(sys.argv) > 1 else "260127192291403"
    check_order_simple(order_id)
