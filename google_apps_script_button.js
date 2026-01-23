/**
 * Google Apps Script code to create a button that triggers sync
 * 
 * Instructions:
 * 1. Open your Google Sheet
 * 2. Go to Extensions > Apps Script
 * 3. Paste this code
 * 4. Save the project
 * 5. Create a button in your sheet:
 *    - Insert > Drawing > Create a button shape
 *    - Right-click the button > Assign script > enter "triggerSync"
 * 
 * OR use a cell-based trigger:
 * - Add a column "Sync Trigger" in row 7
 * - When you want to sync, type "TRIGGER" or "SYNC" in any account row in that column
 * - The Python listener will detect it and run the sync
 */

function triggerSync() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var triggerCol = findTriggerColumn(sheet);
  
  if (triggerCol === -1) {
    // If trigger column doesn't exist, create it
    var lastCol = sheet.getLastColumn();
    sheet.getRange(7, lastCol + 1).setValue("Sync Trigger");
    triggerCol = lastCol + 1;
  }
  
  // Set trigger value in first data row (row 8)
  // You can modify this to set it in a specific row
  var triggerRow = 8;
  sheet.getRange(triggerRow, triggerCol).setValue("TRIGGER");
  
  // Show confirmation (only if UI is available - i.e., when called from button)
  try {
    var ui = SpreadsheetApp.getUi();
    ui.alert('Sync trigger activated! The Python listener will process this shortly.');
  } catch (e) {
    // If UI is not available (e.g., running from editor), just log it
    Logger.log('Sync trigger activated! The Python listener will process this shortly.');
  }
}

function findTriggerColumn(sheet) {
  var headerRow = 7;
  var headers = sheet.getRange(headerRow, 1, 1, sheet.getLastColumn()).getValues()[0];
  
  for (var i = 0; i < headers.length; i++) {
    if (headers[i] && headers[i].toString().toLowerCase().includes("sync trigger")) {
      return i + 1; // Return 1-indexed column
    }
  }
  return -1;
}

/**
 * Alternative: Simple function to set trigger in a specific cell
 * You can call this from a button or manually
 */
function setSyncTrigger() {
  var sheet = SpreadsheetApp.getActiveSheet();
  
  // Find or create Sync Trigger column
  var triggerCol = findTriggerColumn(sheet);
  if (triggerCol === -1) {
    var lastCol = sheet.getLastColumn();
    sheet.getRange(7, lastCol + 1).setValue("Sync Trigger");
    triggerCol = lastCol + 1;
  }
  
  // Set trigger in row 8 (first data row)
  sheet.getRange(8, triggerCol).setValue("TRIGGER");
  
  // Show confirmation (only if UI is available)
  try {
    var ui = SpreadsheetApp.getUi();
    ui.alert('Sync triggered!');
  } catch (e) {
    Logger.log('Sync triggered!');
  }
}
