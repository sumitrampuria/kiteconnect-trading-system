#!/usr/bin/env python3
"""
Script to check order status and error details for a specific order ID.
"""
import json
import datetime
import os
import sys
from kiteconnect import KiteConnect
from google_sheets_reader import get_all_accounts_from_google_sheet

def initialize_kite_for_account(account):
    """Initialize KiteConnect for an account."""
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
        return None
    except:
        return None

def check_order_status(order_id):
    """Check order status for a given order ID across all accounts."""
    print(f"Checking order status for Order ID: {order_id}")
    print("="*80)
    
    # Load all accounts
    try:
        accounts = get_all_accounts_from_google_sheet(
            spreadsheet_id="1bz-TvpcGnUpzD59sPnbLOtjrRpb4U4v_B-Pohgd3ZU4",
            gid=736151233,
            header_row=7,
            data_start_row=8
        )
    except Exception as e:
        print(f"Error loading accounts: {e}")
        return
    
    # Check order in each account
    found = False
    for account in accounts:
        kite = initialize_kite_for_account(account)
        if not kite:
            continue
        
        try:
            # Get order history for this order ID
            order_history = kite.order_history(order_id)
            
            if order_history:
                found = True
                account_name = account.get('account_holder_name', 'Unknown')
                account_kite_id = account.get('account_kite_id', 'Unknown')
                
                print(f"\nFound in account: {account_name} ({account_kite_id})")
                print("-"*80)
                
                # Print order details
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
                    print(f"Exchange Update Timestamp: {order.get('exchange_update_timestamp')}")
                    
                    # Check for error details
                    if order.get('status') in ['REJECTED', 'CANCELLED']:
                        print(f"\n⚠️  ORDER FAILED:")
                        print(f"   Status: {order.get('status')}")
                        print(f"   Error Message: {order.get('status_message')}")
                        print(f"   Raw Error: {order.get('status_message_raw')}")
                    
                    print("-"*80)
                
        except Exception as e:
            # Order not found in this account or error
            continue
    
    if not found:
        print(f"\nOrder ID {order_id} not found in any account.")
        print("Note: Order IDs are account-specific. Make sure you're checking the correct account.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_order_status.py <order_id>")
        print("Example: python check_order_status.py 260127192071195")
        sys.exit(1)
    
    order_id = sys.argv[1]
    check_order_status(order_id)
