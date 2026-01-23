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
SPREADSHEET_ID = "1bz-TvpcGnUpzD59sPnbLOtjrRpb4U4v_B-Pohgd3ZU4"
GID = 736151233
TRIGGER_COLUMN_NAME = "Sync Trigger"  # Column name in Google Sheet
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
        print(f"✓ Cleared trigger in row {row_num}")
    except Exception as e:
        print(f"Error clearing trigger: {e}")


def run_sync():
    """Run the position sync process by executing sync_operations.py."""
    print("\n" + "="*80)
    print(f"SYNC TRIGGERED AT: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
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


def main_listener_loop():
    """Main loop that listens for triggers."""
    print("="*80)
    print("GOOGLE SHEETS SYNC LISTENER")
    print("="*80)
    print(f"Polling interval: {POLL_INTERVAL} seconds")
    print(f"Trigger column: {TRIGGER_COLUMN_NAME}")
    print(f"Trigger values: {', '.join(TRIGGER_VALUES)}")
    print("="*80)
    print("\nListening for sync triggers...")
    print("(Press Ctrl+C to stop)\n")
    
    client = get_google_sheets_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    if GID:
        try:
            worksheet = spreadsheet.get_worksheet_by_id(int(GID))
        except:
            worksheet = spreadsheet.sheet1
    else:
        worksheet = spreadsheet.sheet1
    
    trigger_col = find_trigger_column(worksheet, TRIGGER_ROW)
    
    if not trigger_col:
        print(f"⚠️  Warning: '{TRIGGER_COLUMN_NAME}' column not found in row {TRIGGER_ROW}")
        print("   Please add a column named 'Sync Trigger' in your Google Sheet")
        print("   The listener will continue but won't detect triggers.")
        print("   You can add the column later and restart the listener.\n")
    
    last_trigger_time = None
    last_trigger_row = None
    
    try:
        while True:
            if trigger_col:
                row_num, trigger_value = check_trigger(worksheet, trigger_col, data_start_row=8)
                
                if row_num and (row_num != last_trigger_row or time.time() - (last_trigger_time or 0) > 10):
                    # New trigger detected
                    current_time = time.time()
                    print(f"\n🔔 Trigger detected in row {row_num}: '{trigger_value}'")
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
