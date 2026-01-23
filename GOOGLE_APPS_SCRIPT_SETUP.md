# Google Apps Script Button Setup - Detailed Guide

This guide will walk you through setting up a clickable button in your Google Sheet that triggers position syncing.

## Overview

The Google Apps Script button provides a user-friendly way to trigger syncs:
- **One-click sync** - Just click the button
- **Visual feedback** - Button appears in your sheet
- **No manual typing** - No need to type "TRIGGER" in cells
- **Professional interface** - Clean, integrated solution

## Step-by-Step Setup

### Step 1: Open Google Apps Script Editor

1. Open your Google Sheet:
   https://docs.google.com/spreadsheets/d/1bz-TvpcGnUpzD59sPnbLOtjrRpb4U4v_B-Pohgd3ZU4

2. Click on **Extensions** in the menu bar (top)

3. Select **Apps Script** from the dropdown

4. A new tab will open with the Apps Script editor

### Step 2: Add the Script Code

1. In the Apps Script editor, you'll see a default function like:
   ```javascript
   function myFunction() {
   
   }
   ```

2. **Delete all existing code** in the editor

3. Open the file `google_apps_script_button.js` from your project folder

4. **Copy the entire contents** of that file

5. **Paste it** into the Apps Script editor

6. You should now see two functions:
   - `triggerSync()` - Main function for the button
   - `setSyncTrigger()` - Alternative function
   - `findTriggerColumn()` - Helper function

7. Click the **Save** icon (floppy disk) or press `Ctrl+S` (Windows) / `Cmd+S` (Mac)

8. Give your project a name (e.g., "Position Sync Trigger") when prompted

### Step 3: Authorize the Script (First Time Only)

1. Click the **Run** button (▶️) next to any function name

2. Google will ask for authorization:
   - Click **Review Permissions**
   - Select your Google account
   - Click **Advanced** (if shown)
   - Click **Go to [Project Name] (unsafe)** - This is safe, it's your own script
   - Click **Allow**

3. The script needs these permissions:
   - **View and manage your spreadsheets** - To read/write the trigger cell
   - This is necessary for the button to work

### Step 4: Create the Button in Your Sheet

**Method 1: Using Drawing (Recommended)**

1. Go back to your Google Sheet tab

2. Click **Insert** in the menu bar

3. Select **Drawing**

4. In the drawing editor:
   - Click the **Shape** icon (rectangle/circle)
   - Choose a rectangle or rounded rectangle
   - Draw a button shape
   - Click the **Text box** icon (T)
   - Type: **"Sync Positions"** or **"Trigger Sync"**
   - Style it: Choose font size, color, etc.
   - Make it look like a button (add background color, border)

5. Click **Save and Close**

6. The button will appear on your sheet

7. **Position the button** where you want it (e.g., top-right corner, near the header row)

**Method 2: Using Image (Alternative)**

1. Insert > Image > Image in cells
2. Upload a button image
3. Position it in your sheet

### Step 5: Assign the Script to the Button

1. **Right-click** on the button you just created

2. Click the **three dots menu** (⋮) that appears

3. Select **Assign script** (or **Link** > **Assign script**)

4. In the dialog box, type: **`triggerSync`** (exactly as shown, case-sensitive)

5. Click **OK**

### Step 6: Test the Button

1. Make sure your Python listener is running:
   ```bash
   cd /Users/sumitrampuria/my_project
   source venv/bin/activate
   python sync_listener.py
   ```

2. In your Google Sheet, **click the button**

3. You should see:
   - A popup message: "Sync trigger activated! The Python listener will process this shortly."
   - The "Sync Trigger" column (if it exists) will have "TRIGGER" set in row 8

4. Check your Python listener terminal - it should detect the trigger and start syncing

## How It Works

### The Script Functions:

**`triggerSync()`** - Main button function:
- Finds or creates the "Sync Trigger" column
- Sets "TRIGGER" value in row 8 (first data row)
- Shows a confirmation popup
- The Python listener detects this and runs the sync

**`findTriggerColumn()`** - Helper function:
- Searches row 7 (header row) for "Sync Trigger" column
- Returns the column number if found

**`setSyncTrigger()`** - Alternative function:
- Same as triggerSync but can be called directly
- Useful for testing or manual triggers

### The Flow:

1. **User clicks button** → `triggerSync()` function executes
2. **Script sets trigger** → Writes "TRIGGER" to Sync Trigger column
3. **Python listener detects** → Polls every 5 seconds, finds the trigger
4. **Sync executes** → `main_copy.py` runs, syncs positions
5. **Trigger cleared** → Python listener clears the trigger value
6. **Ready for next sync** → Button can be clicked again

## Advanced Configuration

### Customize Button Behavior

You can modify the script to:

**1. Set trigger in specific row:**
```javascript
function triggerSync() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var triggerCol = findTriggerColumn(sheet);
  var triggerRow = 8; // Change this to target specific account row
  sheet.getRange(triggerRow, triggerCol).setValue("TRIGGER");
  SpreadsheetApp.getUi().alert('Sync triggered!');
}
```

**2. Add timestamp:**
```javascript
function triggerSync() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var triggerCol = findTriggerColumn(sheet);
  var timestamp = new Date().toLocaleString();
  sheet.getRange(8, triggerCol).setValue("TRIGGER");
  sheet.getRange(9, triggerCol).setValue("Last sync: " + timestamp);
  SpreadsheetApp.getUi().alert('Sync triggered at ' + timestamp);
}
```

**3. Multiple buttons for different accounts:**
```javascript
function triggerSyncAccount1() {
  setTriggerInRow(8); // First account
}

function triggerSyncAccount2() {
  setTriggerInRow(9); // Second account
}

function setTriggerInRow(row) {
  var sheet = SpreadsheetApp.getActiveSheet();
  var triggerCol = findTriggerColumn(sheet);
  sheet.getRange(row, triggerCol).setValue("TRIGGER");
}
```

### Create Multiple Buttons

You can create different buttons for different purposes:

1. **"Sync All"** button → Assigns `triggerSync()`
2. **"Sync Account 1"** button → Assigns custom function
3. **"Test Sync"** button → Assigns test function

## Troubleshooting

### Button Not Working

**Issue: "Script function not found"**
- Solution: Make sure function name is exactly `triggerSync` (case-sensitive)
- Check that the script is saved in Apps Script editor

**Issue: "You do not have permission"**
- Solution: Re-authorize the script (Step 3)
- Go to Apps Script > Run > triggerSync
- Grant permissions again

**Issue: Button does nothing**
- Solution: Check browser console (F12) for errors
- Verify the script is saved
- Make sure "Sync Trigger" column exists or script will create it

### Script Errors

**Error: "Cannot find method"**
- Solution: Make sure you copied the entire script
- Check that all three functions are present

**Error: "Range not found"**
- Solution: The script tries to create the column automatically
- Manually add "Sync Trigger" column in row 7 if needed

### Python Listener Not Detecting

**Issue: Listener doesn't see trigger**
- Solution: Check that "Sync Trigger" column name matches exactly
- Verify trigger value is set in a data row (row 8 or below)
- Check Python listener logs for errors

## Best Practices

1. **Button Placement:**
   - Place button in a fixed location (e.g., top-right)
   - Don't place it in rows/columns that might be deleted
   - Consider freezing the row/column where button is placed

2. **Button Design:**
   - Use clear, visible colors
   - Add text like "Sync Positions" or "🔄 Sync"
   - Make it large enough to click easily

3. **Error Handling:**
   - The script includes basic error handling
   - Check Python listener logs if sync doesn't work
   - Verify all accounts are properly initialized

4. **Security:**
   - Only you (and authorized users) can trigger syncs
   - The script only modifies the trigger cell
   - No sensitive data is exposed

## Alternative: Quick Action Menu

Instead of a button, you can add a custom menu:

Add this to your Apps Script:

```javascript
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('Position Sync')
      .addItem('Trigger Sync', 'triggerSync')
      .addItem('Test Connection', 'testConnection')
      .addToUi();
}

function testConnection() {
  SpreadsheetApp.getUi().alert('Testing connection to Python listener...');
  triggerSync();
}
```

This creates a custom menu "Position Sync" in your Google Sheet menu bar with options to trigger sync.

## Summary

The Google Apps Script button provides:
- ✅ One-click sync triggering
- ✅ Professional interface
- ✅ Visual feedback
- ✅ Easy to use
- ✅ No manual cell editing needed

Once set up, you just click the button whenever you want to sync positions!
