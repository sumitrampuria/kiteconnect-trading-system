#!/usr/bin/env python3
"""
Continuous listener for Google Sheets sync trigger.
Polls Google Sheets for a trigger button press and executes position syncing.
"""
import time
import json
import datetime
import os
import sys
import subprocess

# Configuration
SPREADSHEET_ID = "1h9r9DyHgXX39EysPEzZDn70mBM7jQa-I1l8u6bl92M4"
GID = 736151233
TRIGGER_COLUMN_NAME = "Sync Trigger"  # Column name in Google Sheet
TRADING_MECHANISM_ROW = 4  # Row 4 contains "Trading Mechanism" setting
TRADING_MECHANISM_COLUMN_NAME = "Trading Mechanism"  # Column name for trading mechanism
POLL_INTERVAL = 5  # Check every 5 seconds
TRIGGER_ROW = 7  # Header row where trigger column should be
TRIGGER_VALUES = ["TRIGGER", "SYNC", "RUN", "1", "YES"]  # Values that trigger sync


def get_google_sheets_client():
    """Get authenticated Google Sheets client."""
    import gspread
    from google.oauth2.service_account import Credentials
    
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    client = None
    
    # Try service account file
    default_paths = ['service_account.json', 'credentials.json', 'google_credentials.json']
    for path in default_paths:
        if os.path.exists(path):
            creds = Credentials.from_service_account_file(path, scopes=scope)
            client = gspread.authorize(creds)
            print(f"✓ Authenticated using: {path}")
            break
    
    if client is None:
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            creds = Credentials.from_service_account_file(
                os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), scopes=scope
            )
            client = gspread.authorize(creds)
            print("✓ Authenticated using GOOGLE_APPLICATION_CREDENTIALS")
    
    if client is None:
        raise Exception("Could not authenticate with Google Sheets")
    
    return client


def find_trigger_column(worksheet, header_row=7):
    """Find the column index for the trigger column."""
    try:
        headers = worksheet.row_values(header_row)
        for idx, header in enumerate(headers):
            if header and TRIGGER_COLUMN_NAME.lower() in str(header).lower():
                return idx + 1  # gspread uses 1-indexed
        return None
    except Exception as e:
        print(f"Error finding trigger column: {e}")
        return None


def find_trading_mechanism_column(worksheet, row=4):
    """Find the column index for the Trading Mechanism column in row 4."""
    try:
        row_values = worksheet.row_values(row)
        for idx, value in enumerate(row_values):
            if value and TRADING_MECHANISM_COLUMN_NAME.lower() in str(value).lower():
                # The value itself is the header, return the next column (where the value should be)
                # Actually, we need to find where the value "Button Based" or "Auto" is
                # Let's search for a column header that matches
                return idx + 1  # gspread uses 1-indexed
        return None
    except Exception as e:
        print(f"Error finding trading mechanism column: {e}")
        return None


def get_trading_mechanism(worksheet):
    """Get the Trading Mechanism value from row 4, specifically checking cell B4 (column 2)."""
    try:
        # Method 1: Directly read cell B4 (row 4, column 2)
        try:
            cell_b4 = worksheet.cell(TRADING_MECHANISM_ROW, 2).value  # B4 = row 4, column 2
            if cell_b4:
                value_upper = str(cell_b4).strip().upper()
                if value_upper in ["BUTTON BASED", "AUTO"]:
                    return value_upper
        except:
            pass
        
        # Method 2: Read entire row 4 and search for the value
        row_values = worksheet.row_values(TRADING_MECHANISM_ROW)
        
        # First, try to find "Trading Mechanism" header and get value from adjacent cell
        for idx, value in enumerate(row_values):
            if value and TRADING_MECHANISM_COLUMN_NAME.lower() in str(value).lower():
                # Found the header, check the next column for the value
                if idx + 1 < len(row_values):
                    next_value = row_values[idx + 1]
                    if next_value and str(next_value).strip().upper() in ["BUTTON BASED", "AUTO"]:
                        return str(next_value).strip().upper()
                
                # If not in next column, try a few columns to the right
                try:
                    for check_col in range(idx + 2, min(idx + 6, len(row_values) + 1)):
                        if check_col <= len(row_values):
                            check_value = row_values[check_col - 1] if check_col - 1 < len(row_values) else ""
                            if check_value and str(check_value).strip().upper() in ["BUTTON BASED", "AUTO"]:
                                return str(check_value).strip().upper()
                except:
                    pass
        
        # Method 3: Fallback - search all of row 4 for "Button Based" or "Auto" values
        for value in row_values:
            if value:
                value_upper = str(value).strip().upper()
                if value_upper in ["BUTTON BASED", "AUTO"]:
                    return value_upper
        
        return None
    except Exception as e:
        # Silently return None on error (will default to button-based)
        return None


def check_trigger(worksheet, trigger_col, data_start_row=8):
    """Check if trigger is activated in any account row."""
    try:
        # Check all data rows for trigger value
        for row_num in range(data_start_row, min(worksheet.row_count + 1, data_start_row + 20)):  # Check first 20 rows
            try:
                cell_value = worksheet.cell(row_num, trigger_col).value
                if cell_value and str(cell_value).strip().upper() in [v.upper() for v in TRIGGER_VALUES]:
                    return row_num, cell_value
            except:
                continue
        return None, None
    except Exception as e:
        print(f"Error checking trigger: {e}")
        return None, None


def clear_trigger(worksheet, row_num, trigger_col):
    """Clear the trigger after processing."""
    try:
        worksheet.update_cell(row_num, trigger_col, "")
    except Exception as e:
        print(f"Error clearing trigger: {e}")


def run_sync():
    """Run the position sync process by executing sync_operations.py."""
    try:
        # Run the sync_operations.py script which handles syncing (lightweight, no verbose init)
        script_path = os.path.join(os.path.dirname(__file__), 'sync_operations.py')
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=False,
            text=True,
            cwd=os.path.dirname(__file__)
        )
        return result.returncode == 0
    except Exception as e:
        print(f"✗ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_accounts_config():
    """Load account configuration from local file."""
    config_file = "accounts_config.json"
    if not os.path.exists(config_file):
        raise Exception(f"Account configuration file '{config_file}' not found. Please run main.py first to generate it.")
    
    with open(config_file, "r") as f:
        config = json.load(f)
    
    trading_mechanism = config.get("trading_mechanism", "BUTTON BASED")
    accounts = config.get("accounts", [])
    
    return trading_mechanism, accounts


def main_listener_loop():
    """Main loop that listens for triggers."""
    print("="*80)
    print("GOOGLE SHEETS SYNC LISTENER")
    print("="*80)
    print("\nLoading account configuration from local file...")
    
    # Load config from local file
    try:
        trading_mechanism, accounts_config = load_accounts_config()
        print(f"✓ Loaded configuration for {len(accounts_config)} account(s)")
    except Exception as e:
        print(f"✗ Failed to load account configuration: {e}")
        print("Please run main.py first to generate accounts_config.json")
        return
    
    print("\nListening for sync triggers...")
    print("(Press Ctrl+C to stop)\n")
    
    # Only connect to Google Sheets if trading mechanism is Button Based
    client = None
    spreadsheet = None
    worksheet = None
    
    if trading_mechanism == "BUTTON BASED":
        try:
            client = get_google_sheets_client()
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            
            if GID:
                try:
                    worksheet = spreadsheet.get_worksheet_by_id(int(GID))
                except:
                    worksheet = spreadsheet.sheet1
            else:
                worksheet = spreadsheet.sheet1
            print("✓ Connected to Google Sheets for trigger detection")
        except Exception as e:
            print(f"⚠️  Warning: Could not connect to Google Sheets: {e}")
            print("   Button-based triggers will not work. Please check your connection.")
    else:
        print("✓ Auto mode: No Google Sheets connection needed")
    
    # Determine and print the mode
    if trading_mechanism == "AUTO":
        print(f"✓ Trading Mechanism: AUTO")
        print("  - First sync will run immediately")
        print("  - Subsequent syncs will run at seconds = 0 of each minute\n")
    elif trading_mechanism == "BUTTON BASED":
        print(f"✓ Trading Mechanism: BUTTON BASED")
        print("  - Sync will only run when button is clicked\n")
    else:
        # Unknown or missing - default to button-based
        trading_mechanism = "BUTTON BASED"
        print(f"⚠️  Trading Mechanism unknown, defaulting to: BUTTON BASED")
        print("  - Sync will only run when button is clicked\n")
    
    # Only check for Sync Trigger column if we're in Button Based mode and have worksheet
    trigger_col = None
    if trading_mechanism == "BUTTON BASED" and worksheet:
        trigger_col = find_trigger_column(worksheet, TRIGGER_ROW)
        
        if not trigger_col:
            print(f"⚠️  Warning: '{TRIGGER_COLUMN_NAME}' column not found in row {TRIGGER_ROW}")
            print("   Please add a column named 'Sync Trigger' in your Google Sheet")
            print("   The listener will continue but won't detect button-based triggers.")
            print("   You can add the column later and restart the listener.\n")
    
    last_trigger_time = None
    last_trigger_row = None
    last_auto_trigger_minute = None  # Track last minute when auto trigger fired
    first_auto_trigger_done = False  # Track if first trigger has been executed
    
    try:
        while True:
            # Use the trading mechanism determined at startup (not re-checking)
            
            if trading_mechanism == "AUTO":
                # AUTO mode: First trigger happens immediately, then at end of each minute
                current_time = datetime.datetime.now()
                current_minute = current_time.minute
                current_second = current_time.second
                
                # First trigger: execute immediately on startup (only for AUTO mode)
                if not first_auto_trigger_done:
                    print(f"\n🔄 Auto trigger (first run) at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    first_auto_trigger_done = True
                    last_auto_trigger_minute = current_minute
                    
                    # Run sync
                    success = run_sync()
                    
                    if success:
                        print("\n✓ Auto sync completed successfully")
                    else:
                        print("\n✗ Auto sync completed with errors")
                    
                    print("\n" + "="*80)
                    print("Resuming auto listener... (Press Ctrl+C to stop)")
                    print("="*80 + "\n")
                
                # Subsequent triggers: at seconds = 0 of each minute
                # Check if we're at 0 seconds and haven't triggered for this minute yet
                elif current_second == 0 and current_minute != last_auto_trigger_minute:
                    print(f"\n🔄 Auto trigger at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    last_auto_trigger_minute = current_minute
                    
                    # Run sync
                    success = run_sync()
                    
                    if success:
                        print("\n✓ Auto sync completed successfully")
                    else:
                        print("\n✗ Auto sync completed with errors")
                    
                    print("\n" + "="*80)
                    print("Resuming auto listener... (Press Ctrl+C to stop)")
                    print("="*80 + "\n")
                
                # Use shorter polling interval for AUTO mode to catch second 0 more accurately
                time.sleep(1)  # Check every 1 second in AUTO mode for precision
                continue  # Skip the default sleep at the end
            
            elif trading_mechanism == "BUTTON BASED":
                # Button-based mode: Only trigger when button is clicked (no auto trigger)
                # Reset first_auto_trigger_done flag in case mode switches back to AUTO later
                first_auto_trigger_done = False
                
                # Check for button trigger (only if we have worksheet connection)
                if worksheet and trigger_col:
                    row_num, trigger_value = check_trigger(worksheet, trigger_col, data_start_row=8)
                    
                    if row_num and (row_num != last_trigger_row or time.time() - (last_trigger_time or 0) > 10):
                        # New trigger detected
                        current_time = time.time()
                        clear_trigger(worksheet, row_num, trigger_col)
                        
                        # Run sync
                        success = run_sync()
                        
                        if success:
                            print("\n✓ Sync completed successfully")
                        else:
                            print("\n✗ Sync completed with errors")
                        
                        last_trigger_time = current_time
                        last_trigger_row = row_num
                        print("\n" + "="*80)
                        print("Resuming listener... (Press Ctrl+C to stop)")
                        print("="*80 + "\n")
                elif not worksheet:
                    # No Google Sheets connection - wait a bit longer before checking again
                    time.sleep(5)
                    continue
                
                # Use shorter polling interval for Button Based mode to reduce lag
                time.sleep(1)  # Check every 1 second for faster trigger detection
                continue  # Skip the default sleep at the end
            else:
                # This should not happen since we set trading_mechanism to "BUTTON BASED" at startup if unknown
                # But keeping this as a safety fallback
                # Reset first_auto_trigger_done flag
                first_auto_trigger_done = False
                
                # Check for button trigger (only if we have worksheet connection)
                if worksheet and trigger_col:
                    row_num, trigger_value = check_trigger(worksheet, trigger_col, data_start_row=8)
                    
                    if row_num and (row_num != last_trigger_row or time.time() - (last_trigger_time or 0) > 10):
                        current_time = time.time()
                        clear_trigger(worksheet, row_num, trigger_col)
                        
                        success = run_sync()
                        
                        if success:
                            print("\n✓ Sync completed successfully")
                        else:
                            print("\n✗ Sync completed with errors")
                        
                        last_trigger_time = current_time
                        last_trigger_row = row_num
                        print("\n" + "="*80)
                        print("Resuming listener... (Press Ctrl+C to stop)")
                        print("="*80 + "\n")
            
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        print("Listener stopped by user")
        print("="*80)
    except Exception as e:
        print(f"\n✗ Fatal error in listener: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main_listener_loop()
