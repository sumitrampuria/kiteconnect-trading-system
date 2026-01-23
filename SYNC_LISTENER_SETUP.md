# Google Sheets Sync Trigger Setup Guide

This guide explains how to set up the Google Sheets button trigger for automatic position syncing.

## Overview

The system consists of:
1. **Python Listener** (`sync_listener.py`) - Runs continuously, polling Google Sheets for triggers
2. **Google Apps Script Button** - Button in Google Sheets that sets a trigger value
3. **Main Sync Script** (`main_copy.py`) - Executes the actual position syncing

## Setup Steps

### Step 1: Add "Sync Trigger" Column to Google Sheet

1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1bz-TvpcGnUpzD59sPnbLOtjrRpb4U4v_B-Pohgd3ZU4
2. In **row 7** (header row), add a new column named **"Sync Trigger"**
3. This column will be used to trigger syncs

### Step 2: Set Up Google Apps Script Button (Optional but Recommended)

**Option A: Using Apps Script Button**

1. In your Google Sheet, go to **Extensions > Apps Script**
2. Delete any existing code
3. Copy and paste the contents of `google_apps_script_button.js`
4. Click **Save** (floppy disk icon)
5. Go back to your sheet
6. **Insert > Drawing** - Create a button shape (e.g., rectangle with text "Sync Positions")
7. Click **Save and Close**
8. Right-click the button > **Assign script** > Enter: `triggerSync`
9. Click **OK**

**Option B: Manual Cell Entry (Simpler)**

1. Just type **"TRIGGER"**, **"SYNC"**, or **"RUN"** in the "Sync Trigger" column in any account row (row 8 or below)
2. The Python listener will detect it automatically

### Step 3: Run the Python Listener

```bash
cd /Users/sumitrampuria/my_project
source venv/bin/activate
python sync_listener.py
```

The listener will:
- Poll Google Sheets every 5 seconds
- Detect when "TRIGGER", "SYNC", "RUN", "1", or "YES" appears in the "Sync Trigger" column
- Automatically run the sync process
- Clear the trigger after processing
- Display updated positions for all accounts

### Step 4: Keep Listener Running

The listener runs indefinitely until you stop it (Ctrl+C). For production use, consider:

**Option A: Run in Background**
```bash
nohup python sync_listener.py > listener.log 2>&1 &
```

**Option B: Use screen/tmux**
```bash
screen -S sync_listener
python sync_listener.py
# Press Ctrl+A then D to detach
# Reattach with: screen -r sync_listener
```

**Option C: Create a System Service (Linux/Mac)**
Create a service file to run it automatically on system startup.

## How It Works

1. **User Action**: Click the button in Google Sheets OR type "TRIGGER" in the Sync Trigger column
2. **Detection**: Python listener polls every 5 seconds and detects the trigger
3. **Sync Execution**: `main_copy.py` is executed, which:
   - Initializes all accounts
   - Gets base account positions
   - Calculates proportional quantities
   - Places delta trades in target accounts (where Copy Trades = YES)
   - Prints updated positions for all accounts
4. **Cleanup**: Trigger is cleared from the sheet
5. **Resume**: Listener continues polling for next trigger

## Trigger Values

The following values in the "Sync Trigger" column will trigger a sync:
- `TRIGGER`
- `SYNC`
- `RUN`
- `1`
- `YES`

(All case-insensitive)

## Troubleshooting

**Listener not detecting triggers:**
- Check that "Sync Trigger" column exists in row 7
- Verify the column name matches exactly (case-insensitive)
- Check that you're typing the trigger value in a data row (row 8 or below)

**Sync not executing:**
- Check that all accounts have valid credentials
- Verify base account has KiteConnect initialized
- Check that target accounts have "Copy Trades" = "YES"

**Button not working:**
- Make sure Apps Script is saved
- Verify script name matches: `triggerSync`
- Check browser console for errors (F12)

## Configuration

You can modify these settings in `sync_listener.py`:

```python
POLL_INTERVAL = 5  # Check every 5 seconds (adjust as needed)
TRIGGER_COLUMN_NAME = "Sync Trigger"  # Column name
TRIGGER_ROW = 7  # Header row number
TRIGGER_VALUES = ["TRIGGER", "SYNC", "RUN", "1", "YES"]  # Valid trigger values
```

## Notes

- The listener must be running continuously to detect triggers
- Each trigger is processed only once (prevents duplicate syncs)
- The sync process includes full account initialization, so it may take 10-30 seconds
- All positions are displayed after each sync for verification
