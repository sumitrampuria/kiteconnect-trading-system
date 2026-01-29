#!/usr/bin/env python3
"""
Quick script to check a single order status.
Usage: python check_single_order.py <order_id> [account_kite_id]
"""
import json
import datetime
import os
import sys
from kiteconnect import KiteConnect

def check_order_status(order_id, account_kite_id=None):
    """Check order status for a specific order ID."""
    print(f"Checking order: {order_id}")
    print("="*80)
    
    # Load accounts from Google Sheets
    try:
        from google_sheets_reader import get_all_accounts_from_google_sheet
        
        accounts = get_all_accounts_from_google_sheet(
            spreadsheet_id="1h9r9DyHgXX39EysPEzZDn70mBM7jQa-I1l8u6bl92M4",
            gid=736151233,
            header_row=7,
            data_start_row=8
        )
        
        # Filter by account_kite_id if provided
        if account_kite_id:
            accounts = [acc for acc in accounts if acc.get('account_kite_id') == account_kite_id]
        
        found = False
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
                            found = True
                            print(f"\n✓ Found order in account: {account.get('account_holder_name')} ({kite_id})")
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
                                print(f"Exchange Update Timestamp: {order.get('exchange_update_timestamp')}")
                                
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
            except Exception as e:
                continue
        
        if not found:
            print(f"\n✗ Order {order_id} not found in any account.")
            print("Note: Order IDs are account-specific.")
            print("Make sure you're checking the correct account.")
        
    except ImportError:
        print("Cannot import google_sheets_reader. Please run from project directory.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    order_id = sys.argv[1] if len(sys.argv) > 1 else None
    account_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not order_id:
        print("Usage: python check_single_order.py <order_id> [account_kite_id]")
        print("Example: python check_single_order.py 260127192291403")
        sys.exit(1)
    
    check_order_status(order_id, account_id)
