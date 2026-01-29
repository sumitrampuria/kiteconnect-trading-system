#!/usr/bin/env python3
"""
Module to read credentials from Google Sheets.
"""
import os
import gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow


def get_credentials_from_google_sheet(
    spreadsheet_id="1h9r9DyHgXX39EysPEzZDn70mBM7jQa-I1l8u6bl92M4",
    sheet_name=None,
    gid=None,
    service_account_file=None,
    oauth_credentials_file=None
):
    """
    Read API_Key and API_Secret from Google Sheets.
    
    Args:
        spreadsheet_id: The Google Sheets spreadsheet ID
        sheet_name: Name of the sheet/tab (optional, if not provided will use first sheet)
        gid: Sheet GID (optional, alternative to sheet_name)
        service_account_file: Path to service account JSON file (recommended method)
        oauth_credentials_file: Path to OAuth credentials JSON file (alternative method)
    
    Returns:
        dict: Dictionary with 'api_key' and 'api_secret' keys
    
    Raises:
        Exception: If authentication fails or values cannot be found
    """
    # Authenticate with Google Sheets API
    scope = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    client = None
    
    # Method 1: Service Account (Recommended for server-side applications)
    if service_account_file and os.path.exists(service_account_file):
        creds = Credentials.from_service_account_file(service_account_file, scopes=scope)
        client = gspread.authorize(creds)
        print(f"Authenticated using service account: {service_account_file}")
    
    # Method 2: OAuth (For user-based authentication)
    elif oauth_credentials_file and os.path.exists(oauth_credentials_file):
        flow = InstalledAppFlow.from_client_secrets_file(
            oauth_credentials_file, scope
        )
        creds = flow.run_local_server(port=0)
        client = gspread.authorize(creds)
        print(f"Authenticated using OAuth credentials: {oauth_credentials_file}")
    
    # Method 3: Try to use service account from environment variable
    elif os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        creds = Credentials.from_service_account_file(
            os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), scopes=scope
        )
        client = gspread.authorize(creds)
        print("Authenticated using GOOGLE_APPLICATION_CREDENTIALS environment variable")
    
    # Method 4: Try default service account file names
    else:
        default_paths = [
            'service_account.json',
            'credentials.json',
            'google_credentials.json'
        ]
        for path in default_paths:
            if os.path.exists(path):
                creds = Credentials.from_service_account_file(path, scopes=scope)
                client = gspread.authorize(creds)
                print(f"Authenticated using default file: {path}")
                break
    
    if client is None:
        raise Exception(
            "Could not authenticate with Google Sheets. Please provide one of:\n"
            "1. Service account JSON file (recommended)\n"
            "2. OAuth credentials JSON file\n"
            "3. Set GOOGLE_APPLICATION_CREDENTIALS environment variable\n"
            "4. Place service_account.json in the project root"
        )
    
    # Open the spreadsheet
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        print(f"Opened spreadsheet: {spreadsheet.title}")
    except Exception as e:
        raise Exception(f"Failed to open spreadsheet: {e}")
    
    # Select the specific sheet
    if gid:
        # If GID is provided, find the sheet by GID
        try:
            worksheet = spreadsheet.get_worksheet_by_id(int(gid))
            print(f"Using sheet with GID: {gid}")
        except Exception as e:
            print(f"Warning: Could not find sheet with GID {gid}, using first sheet: {e}")
            worksheet = spreadsheet.sheet1
    elif sheet_name:
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            print(f"Using sheet: {sheet_name}")
        except Exception as e:
            print(f"Warning: Could not find sheet '{sheet_name}', using first sheet: {e}")
            worksheet = spreadsheet.sheet1
    else:
        worksheet = spreadsheet.sheet1
        print("Using first sheet")
    
    # Read all values from the worksheet
    all_values = worksheet.get_all_values()
    
    # Debug: Print sheet structure (first few rows)
    print(f"\nSheet structure (first 5 rows):")
    for i, row in enumerate(all_values[:5]):
        print(f"  Row {i}: {row}")
    
    # Search for rows containing "API" to find where credentials are
    print(f"\nSearching for API credentials...")
    api_rows = []
    for i, row in enumerate(all_values):
        row_str = ' '.join(str(cell) for cell in row).lower()
        if 'api' in row_str:
            api_rows.append((i, row))
            print(f"  Found API-related row {i}: {row}")
    
    # Find API_Key and API_Secret
    api_key = None
    api_secret = None
    
    # Method 1: Look for header row with "API_Key" and "API_Secret" columns
    # Search through all rows to find the header row
    api_key_col = None
    api_secret_col = None
    header_row_idx = None
    
    for row_idx, row in enumerate(all_values):
        headers = [str(cell).lower().strip() for cell in row]
        
        # Find column indices in this row
        temp_api_key_col = None
        temp_api_secret_col = None
        
        for idx, header in enumerate(headers):
            # More precise matching - header should be exactly or start with the key name
            if header == 'api_key' or header == 'apikey' or (header.startswith('api_key') and 'secret' not in header):
                temp_api_key_col = idx
            if header == 'api_secret' or header == 'apisecret' or (header.startswith('api_secret') or (header.startswith('api') and 'secret' in header)):
                temp_api_secret_col = idx
        
        # If we found both columns in this row, this is likely the header row
        if temp_api_key_col is not None and temp_api_secret_col is not None:
            api_key_col = temp_api_key_col
            api_secret_col = temp_api_secret_col
            header_row_idx = row_idx
            print(f"  Found header row at index {row_idx}: API_Key in column {api_key_col}, API_Secret in column {api_secret_col}")
            break
        # Or if we found at least one, use it (might be the header row)
        elif temp_api_key_col is not None or temp_api_secret_col is not None:
            if api_key_col is None:
                api_key_col = temp_api_key_col
            if api_secret_col is None:
                api_secret_col = temp_api_secret_col
            if header_row_idx is None:
                header_row_idx = row_idx
    
    # If headers found, read from first data row (row after header)
    if api_key_col is not None or api_secret_col is not None:
        data_row_idx = header_row_idx + 1 if header_row_idx is not None else 1
        if len(all_values) > data_row_idx:
            if api_key_col is not None and api_key_col < len(all_values[data_row_idx]):
                potential_key = str(all_values[data_row_idx][api_key_col]).strip()
                # Skip if the value is actually a header label or empty
                if potential_key and potential_key.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret', '']:
                    api_key = potential_key
                    print(f"  Extracted API_Key from row {data_row_idx}, column {api_key_col}")
            if api_secret_col is not None and api_secret_col < len(all_values[data_row_idx]):
                potential_secret = str(all_values[data_row_idx][api_secret_col]).strip()
                # Skip if the value is actually a header label or empty
                if potential_secret and potential_secret.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret', '']:
                    api_secret = potential_secret
                    print(f"  Extracted API_Secret from row {data_row_idx}, column {api_secret_col}")
    
    # Method 2: Search all rows for key-value pairs (more thorough)
    if not api_key or not api_secret:
        for row_idx, row in enumerate(all_values):
            row_str = ' '.join(str(cell) for cell in row).lower()
            if 'api_key' in row_str or 'apikey' in row_str:
                # Try to find the value in the same row
                for i, cell in enumerate(row):
                    cell_lower = str(cell).lower().strip()
                    if ('api_key' in cell_lower or 'apikey' in cell_lower) and cell_lower not in ['api_secret', 'apisecret']:
                        # Check next cell for value
                        if i + 1 < len(row) and row[i + 1] and str(row[i + 1]).strip():
                            potential_key = str(row[i + 1]).strip()
                            # Make sure it's not a header label
                            if potential_key.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret', '']:
                                api_key = potential_key
                                print(f"  Found API_Key in row {row_idx}, column {i+1}: {potential_key[:10]}...")
                        # Also check previous cell (in case format is value:label)
                        if i > 0 and row[i - 1] and str(row[i - 1]).strip():
                            potential_key = str(row[i - 1]).strip()
                            if potential_key.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret', '']:
                                api_key = potential_key
                                print(f"  Found API_Key in row {row_idx}, column {i-1}: {potential_key[:10]}...")
                        break
            if 'api_secret' in row_str or 'apisecret' in row_str:
                for i, cell in enumerate(row):
                    cell_lower = str(cell).lower().strip()
                    if ('api_secret' in cell_lower or 'apisecret' in cell_lower):
                        # Check next cell for value
                        if i + 1 < len(row) and row[i + 1] and str(row[i + 1]).strip():
                            potential_secret = str(row[i + 1]).strip()
                            # Make sure it's not a header label
                            if potential_secret.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret', '']:
                                api_secret = potential_secret
                                print(f"  Found API_Secret in row {row_idx}, column {i+1}")
                        # Also check previous cell (in case format is value:label)
                        if i > 0 and row[i - 1] and str(row[i - 1]).strip():
                            potential_secret = str(row[i - 1]).strip()
                            if potential_secret.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret', '']:
                                api_secret = potential_secret
                                print(f"  Found API_Secret in row {row_idx}, column {i-1}")
                        break
    
    # Method 3: If still not found, assume first two columns or first two rows
    # But skip header rows
    if not api_key or not api_secret:
        if len(all_values) >= 2:
            # Try first two rows, first column (skip if it looks like a header)
            if not api_key and all_values[0][0]:
                val = all_values[0][0].strip()
                if val.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret']:
                    api_key = val
            if not api_secret and len(all_values) > 1 and all_values[1][0]:
                val = all_values[1][0].strip()
                if val.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret']:
                    api_secret = val
        
        # Or try first row, first two columns (skip if it looks like a header)
        if (not api_key or not api_secret) and len(all_values) > 0 and len(all_values[0]) >= 2:
            if not api_key and all_values[0][0]:
                val = all_values[0][0].strip()
                if val.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret']:
                    api_key = val
            if not api_secret and all_values[0][1]:
                val = all_values[0][1].strip()
                if val.lower() not in ['api_key', 'apikey', 'api_secret', 'apisecret']:
                    api_secret = val
    
    if not api_key or not api_secret:
        raise Exception(
            f"Could not find API_Key and API_Secret in the Google Sheet.\n"
            f"Please ensure the sheet contains columns named 'API_Key' and 'API_Secret',\n"
            f"or the values are in the first two cells.\n"
            f"Sheet contents preview:\n{all_values[:5]}"
        )
    
    return {
        'api_key': api_key,
        'api_secret': api_secret
    }


def get_all_accounts_from_google_sheet(
    spreadsheet_id="1h9r9DyHgXX39EysPEzZDn70mBM7jQa-I1l8u6bl92M4",
    sheet_name=None,
    gid=None,
    header_row=7,  # Row 7 (1-indexed) = index 6 (0-indexed)
    data_start_row=8,  # Row 8 (1-indexed) = index 7 (0-indexed)
    service_account_file=None,
    oauth_credentials_file=None
):
    """
    Read all accounts from Google Sheets.
    
    Expected columns in header row (row 7):
    - Account Holder Name
    - Account KITE-ID
    - API_Key
    - API_Secret
    - Request URL by Zerodha
    
    Data rows start from row 8 onwards.
    
    Args:
        spreadsheet_id: The Google Sheets spreadsheet ID
        sheet_name: Name of the sheet/tab (optional)
        gid: Sheet GID (optional, alternative to sheet_name)
        header_row: Row number containing headers (1-indexed, default 7)
        data_start_row: First row containing data (1-indexed, default 8)
        service_account_file: Path to service account JSON file
        oauth_credentials_file: Path to OAuth credentials JSON file
    
    Returns:
        list: Array of dictionaries, each containing account details:
            - account_holder_name
            - account_kite_id
            - api_key
            - api_secret
            - request_url_by_zerodha
    """
    # Authenticate with Google Sheets API (same as before)
    scope = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    client = None
    
    # Method 1: Service Account
    if service_account_file and os.path.exists(service_account_file):
        creds = Credentials.from_service_account_file(service_account_file, scopes=scope)
        client = gspread.authorize(creds)
    # Method 2: OAuth
    elif oauth_credentials_file and os.path.exists(oauth_credentials_file):
        flow = InstalledAppFlow.from_client_secrets_file(oauth_credentials_file, scope)
        creds = flow.run_local_server(port=0)
        client = gspread.authorize(creds)
    # Method 3: Environment variable
    elif os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        creds = Credentials.from_service_account_file(
            os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), scopes=scope
        )
        client = gspread.authorize(creds)
    # Method 4: Default file names
    else:
        default_paths = ['service_account.json', 'credentials.json', 'google_credentials.json']
        for path in default_paths:
            if os.path.exists(path):
                creds = Credentials.from_service_account_file(path, scopes=scope)
                client = gspread.authorize(creds)
                break
    
    if client is None:
        raise Exception(
            "Could not authenticate with Google Sheets. Please provide authentication credentials."
        )
    
    # Open the spreadsheet
    spreadsheet = client.open_by_key(spreadsheet_id)
    
    # Select the specific sheet
    if gid:
        try:
            worksheet = spreadsheet.get_worksheet_by_id(int(gid))
        except Exception:
            worksheet = spreadsheet.sheet1
    elif sheet_name:
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception:
            worksheet = spreadsheet.sheet1
    else:
        worksheet = spreadsheet.sheet1
    
    # Read all values from the worksheet
    all_values = worksheet.get_all_values()
    
    # Convert 1-indexed row numbers to 0-indexed
    header_row_idx = header_row - 1  # Row 7 -> index 6
    data_start_row_idx = data_start_row - 1  # Row 8 -> index 7
    
    # Validate that we have enough rows
    if len(all_values) <= header_row_idx:
        raise Exception(f"Sheet does not have row {header_row}. Found only {len(all_values)} rows.")
    
    # Get header row
    header_row_data = all_values[header_row_idx]
    headers = [str(cell).strip() for cell in header_row_data]
    
    # Find column indices for the columns we need
    column_indices = {}
    required_columns = {
        'account_holder_name': ['account holder name', 'account holder', 'holder name'],
        'account_kite_id': ['account kite-id', 'kite-id', 'kite id', 'account kite_id'],
        'api_key': ['api_key', 'api key', 'apikey'],
        'api_secret': ['api_secret', 'api secret', 'apisecret'],
        'request_url_by_zerodha': ['request url by zerodha', 'request url', 'zerodha url'],
        'copy_trades': ['copy trades', 'copy trade', 'copy', 'trades']
    }
    
    for key, possible_names in required_columns.items():
        column_indices[key] = None
        for idx, header in enumerate(headers):
            header_lower = header.lower()
            for name in possible_names:
                if name in header_lower or header_lower in name:
                    column_indices[key] = idx
                    break
            if column_indices[key] is not None:
                break
    
    # Check if we found all required columns (copy_trades is optional)
    required_columns_check = {k: v for k, v in column_indices.items() if k != 'copy_trades'}
    missing_columns = [key for key, idx in required_columns_check.items() if idx is None]
    if missing_columns:
        raise Exception(
            f"Could not find required columns: {', '.join(missing_columns)}\n"
            f"Found headers: {headers}"
        )
    
    # Log if copy_trades column was found
    if column_indices.get('copy_trades') is None:
        print(f"  ⚠️  'Copy Trades' column not found - will default to 'NO' for all accounts")
    
    # Read all data rows starting from data_start_row
    accounts = []
    for row_idx in range(data_start_row_idx, len(all_values)):
        row = all_values[row_idx]
        
        # Skip empty rows
        if not any(cell.strip() for cell in row):
            continue
        
        # Extract values for each column
        account = {}
        for key, col_idx in column_indices.items():
            if col_idx is not None and col_idx < len(row):
                value = str(row[col_idx]).strip()
                account[key] = value if value else None
            else:
                account[key] = None
        
        # Default copy_trades to "NO" if not found or empty
        if account.get('copy_trades') is None or account.get('copy_trades') == '':
            account['copy_trades'] = 'NO'
        
        # Only add account if it has at least API key and secret
        if account.get('api_key') and account.get('api_secret'):
            accounts.append(account)
        elif account.get('account_holder_name') or account.get('account_kite_id'):
            # If there's some data but missing API credentials, still add it (might be incomplete)
            accounts.append(account)
    
    print(f"\nSuccessfully read {len(accounts)} account(s) from the sheet")
    
    return accounts


if __name__ == "__main__":
    # Example usage
    try:
        # Try to read all accounts
        accounts = get_all_accounts_from_google_sheet(
            gid=736151233  # Using the GID from the URL
        )
        print("\nSuccessfully retrieved accounts from Google Sheets:")
        for i, account in enumerate(accounts, 1):
            print(f"\nAccount {i}:")
            print(f"  Account Holder Name: {account.get('account_holder_name', 'N/A')}")
            print(f"  Account KITE-ID: {account.get('account_kite_id', 'N/A')}")
            print(f"  API Key: {account.get('api_key', 'N/A')}")
            print(f"  API Secret: {'*' * len(account.get('api_secret', '')) if account.get('api_secret') else 'N/A'}")
            print(f"  Request URL by Zerodha: {account.get('request_url_by_zerodha', 'N/A')}")
    except Exception as e:
        print(f"Error: {e}")
        print("\nTo use this module, you need to set up Google Sheets API authentication:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable Google Sheets API")
        print("3. Create a Service Account and download the JSON key file")
        print("4. Share your Google Sheet with the service account email")
        print("5. Place the JSON file as 'service_account.json' in the project root")
