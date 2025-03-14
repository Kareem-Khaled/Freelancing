function onEdit(e) {
  var sheet = e.source.getSheetByName('Main');
  var range = e.range;
  var value = range.getValue();
  
  Logger.log("Edit detected at: " + range.getA1Notation());
  Logger.log("Edited Value: " + value);

  var triggerColumns = [1, 4, 5, 7, 9, 11]; // A, D, E, G, I, K
  if (sheet.getName() !== 'Main' || range.getRow() < 4 || range.getRow() > 153 || !triggerColumns.includes(range.getColumn())) {
    Logger.log("Edit outside range. Exiting.");
    return;
  }

  var playerName = sheet.getRange(range.getRow(), 1).getValue(); // A
  var oldPlayerName = e.oldValue; // Previous value before edit
  var column = range.getColumn();

  if (column === 1 && !playerName && oldPlayerName) {
    Logger.log("Player name deleted: " + oldPlayerName);
    removePlayerFromComponents(oldPlayerName, e.source);
    var row = range.getRow();
    sheet.getRange(row, 4).setValue("none");
    var checkboxRange = sheet.getRange(row, 5, 1, 8);
    var newValues = [[0, "", 0, "", 0, "", 0, ""]];
    checkboxRange.setValues(newValues);
    Logger.log("Set D" + row + " to 'none' and reset E:G:I:K to 0, cleared F:H:J:L");
    Logger.log("onEdit complete (name deletion)");
    return;
  }

  if (column === 1 && playerName && oldPlayerName && playerName !== oldPlayerName) {
    Logger.log("Player name changed from " + oldPlayerName + " to " + playerName);
    updatePlayerNameInComponents(oldPlayerName, playerName, sheet, e.source);
    Logger.log("onEdit complete (name change)");
    return;
  }

  var refSheet = e.source.getSheetByName('Reference');
  var compSheet = e.source.getSheetByName('Components');
  var compHeaders = compSheet.getRange(1, 1, 1, 21).getValues()[0]; // A1:U1

  if (column === 4) {
    Logger.log("Item edited in D" + range.getRow());
    var oldItem = e.oldValue;
    if (playerName && oldItem && oldItem.toLowerCase() !== "none") {
      var refData = refSheet.getRange(3, 1, 148, 5).getValues();
      var oldComponents = [];
      for (var i = 0; i < refData.length; i++) {
        if (refData[i][0] === oldItem) {
          oldComponents = refData[i].slice(1, 5).filter(c => c);
          break;
        }
      }
      Logger.log("Old Item: " + oldItem + ", Old Components: " + JSON.stringify(oldComponents));
      for (var j = 0; j < oldComponents.length; j++) {
        var colIndex = compHeaders.indexOf(oldComponents[j]) + 1;
        if (colIndex > 0) {
          var compColumn = compSheet.getRange(2, colIndex, 150, 1);
          var values = compColumn.getValues();
          var backgrounds = compColumn.getBackgrounds();
          var newValues = values.map(row => row[0] === playerName ? [""] : row);
          var newBackgrounds = backgrounds.map((row, idx) => newValues[idx][0] === "" ? ["#ffffff"] : row);
          compColumn.setValues(newValues);
          compColumn.setBackgrounds(newBackgrounds);
          Logger.log("Removed " + playerName + " from column " + colIndex + " (" + oldComponents[j] + ")");
        }
      }
    }
    var checkboxRange = sheet.getRange(range.getRow(), 5, 1, 8);
    var newValues = [[0, "", 0, "", 0, "", 0, ""]];
    checkboxRange.setValues(newValues);
    Logger.log("Reset checkboxes E,G,I,K to 0 and cleared labels F,H,J,L");
  }

  if (!playerName) {
    Logger.log("No player name after checks. Exiting.");
    return;
  }

  var priority = sheet.getRange(range.getRow(), 3).getValue(); // C (1-4)
  var backgroundColor = sheet.getRange(range.getRow(), 3).getBackground(); // C color
  Logger.log("Priority: " + priority + ", Color: " + backgroundColor);

  var checkboxValues = [
    sheet.getRange(range.getRow(), 5).getValue(),  // E
    sheet.getRange(range.getRow(), 7).getValue(),  // G
    sheet.getRange(range.getRow(), 9).getValue(),  // I
    sheet.getRange(range.getRow(), 11).getValue()  // K
  ];
  var componentLabels = [
    sheet.getRange(range.getRow(), 6).getValue(),  // F
    sheet.getRange(range.getRow(), 8).getValue(),  // H
    sheet.getRange(range.getRow(), 10).getValue(), // J
    sheet.getRange(range.getRow(), 12).getValue()  // L
  ];
  Logger.log("Checkbox Values (E,G,I,K): " + JSON.stringify(checkboxValues));
  Logger.log("Components (F,H,J,L): " + JSON.stringify(componentLabels));

  // Check completion and remove from Components
  if ([5, 7, 9, 11].includes(column) && checkboxValues.every(val => val === 1 || val === "1")) {
    var itemBeforeReset = sheet.getRange(range.getRow(), 4).getValue(); // Item before reset
    if (!itemBeforeReset || itemBeforeReset.toLowerCase() === "none") {
      Logger.log("Item already reset to 'none', skipping completion.");
      return;
    }
    Logger.log("All checkboxes checked for " + playerName + " with item " + itemBeforeReset);
    var completedSheet = e.source.getSheetByName('Completed');
    if (!completedSheet) {
      Logger.log("Completed sheet not found. Exiting.");
      return;
    }
    var lock = PropertiesService.getScriptProperties().getProperty('editLock');
    if (lock) {
      Logger.log("Script locked from previous completion, exiting.");
      return;
    }
    PropertiesService.getScriptProperties().setProperty('editLock', 'true');
    try {
      var lastRow = completedSheet.getLastRow();
      var completedData = [];
      if (lastRow > 1) {
        completedData = completedSheet.getRange(2, 1, lastRow - 1, 2).getValues();
      }
      var alreadyLogged = completedData.some(row => row[0] === playerName && row[1] === itemBeforeReset);
      if (alreadyLogged) {
        Logger.log("Completion already logged for " + playerName + " and " + itemBeforeReset + ", skipping.");
        return;
      }
      // Remove player from Components
      var refData = refSheet.getRange(3, 1, 148, 5).getValues();
      var completedComponents = [];
      for (var i = 0; i < refData.length; i++) {
        if (refData[i][0] === itemBeforeReset) {
          completedComponents = refData[i].slice(1, 5).filter(c => c);
          break;
        }
      }
      Logger.log("Completed Item: " + itemBeforeReset + ", Components: " + JSON.stringify(completedComponents));
      for (var j = 0; j < completedComponents.length; j++) {
        var colIndex = compHeaders.indexOf(completedComponents[j]) + 1;
        if (colIndex > 0) {
          var compColumn = compSheet.getRange(2, colIndex, 150, 1);
          var values = compColumn.getValues();
          var backgrounds = compColumn.getBackgrounds();
          var newValues = values.map(row => row[0] === playerName ? [""] : row);
          var newBackgrounds = backgrounds.map((row, idx) => newValues[idx][0] === "" ? ["#ffffff"] : row);
          compColumn.setValues(newValues);
          compColumn.setBackgrounds(newBackgrounds);
          Logger.log("Removed " + playerName + " from column " + colIndex + " (" + completedComponents[j] + ")");
        }
      }
      // Double-check and log to Completed
      lastRow = completedSheet.getLastRow();
      if (lastRow > 1) {
        completedData = completedSheet.getRange(2, 1, lastRow - 1, 2).getValues();
        alreadyLogged = completedData.some(row => row[0] === playerName && row[1] === itemBeforeReset);
        if (alreadyLogged) {
          Logger.log("Completion already logged after refresh for " + playerName + " and " + itemBeforeReset + ", skipping.");
          return;
        }
      }
      completedSheet.getRange(lastRow + 1, 1, 1, 2).setValues([[playerName, itemBeforeReset]]);
      Logger.log("Added " + playerName + " and " + itemBeforeReset + " to Completed sheet at row " + (lastRow + 1));
      // Batch reset Main row *after* Components cleared
      var row = range.getRow();
      sheet.getRange(row, 4, 1, 9).setValues([["none", 0, "", 0, "", 0, "", 0, ""]]);
      Logger.log("Reset D" + row + " to 'none', cleared E:G:I:K and F:H:J:L");
      // Ensure Components are clear
      for (var j = 0; j < completedComponents.length; j++) {
        var colIndex = compHeaders.indexOf(completedComponents[j]) + 1;
        if (colIndex > 0) {
          var compColumn = compSheet.getRange(2, colIndex, 150, 1);
          var values = compColumn.getValues();
          if (values.some(row => row[0] === playerName)) {
            var backgrounds = compColumn.getBackgrounds();
            var newValues = values.map(row => row[0] === playerName ? [""] : row);
            var newBackgrounds = backgrounds.map((row, idx) => newValues[idx][0] === "" ? ["#ffffff"] : row);
            compColumn.setValues(newValues);
            compColumn.setBackgrounds(newBackgrounds);
            Logger.log("Double-checked and removed " + playerName + " from column " + colIndex + " (" + completedComponents[j] + ")");
          }
        }
      }
      Logger.log("Completion processed, exiting onEdit.");
    } finally {
      PropertiesService.getScriptProperties().deleteProperty('editLock');
      Utilities.sleep(100); // Brief delay to let Sheets catch up
    }
    return;
  }

  // Fetch item *after* completion check/reset
  var item = sheet.getRange(range.getRow(), 4).getValue(); // D
  Logger.log("Selected Item: " + item);

  if (!refSheet) {
    Logger.log("Reference sheet not found. Exiting.");
    return;
  }
  var refData = refSheet.getRange(3, 1, 148, 5).getValues();
  var components = [];
  if (item && item.toLowerCase() !== "none") {
    for (var i = 0; i < refData.length; i++) {
      if (refData[i][0] === item) {
        components = refData[i].slice(1, 5).filter(c => c);
        break;
      }
    }
    Logger.log("Components from Reference: " + JSON.stringify(components));
    sheet.getRange(range.getRow(), 6).setValue(components[2] || "");
    sheet.getRange(range.getRow(), 8).setValue(components[3] || "");
    sheet.getRange(range.getRow(), 10).setValue(components[0] || "");
    sheet.getRange(range.getRow(), 12).setValue(components[1] || "");
    Logger.log("Updated component labels in F,H,J,L");
  } else {
    Logger.log("No components fetched (item is none or blank)");
  }

  var checkboxToComponentMap = {
    5: components[2] || "",
    7: components[3] || "",
    9: components[0] || "",
    11: components[1] || ""
  };

  var compHeaders = compSheet.getRange(1, 1, 1, 21).getValues()[0];
  Logger.log("Components Headers: " + JSON.stringify(compHeaders));

  var columnsToCheck = [5, 7, 9, 11];
  for (var i = 0; i < columnsToCheck.length; i++) {
    var col = columnsToCheck[i];
    var component = checkboxToComponentMap[col];
    if (!component) {
      Logger.log("No component for column " + col);
      continue;
    }

    var checkboxValue = checkboxValues[i];
    var componentColumnIndex = compHeaders.indexOf(component) + 1;
    Logger.log("Component: " + component + " -> Column: " + componentColumnIndex + ", Checkbox: " + checkboxValue);

    if (componentColumnIndex === 0) {
      Logger.log("Component " + component + " not in Components sheet");
      continue;
    }

    var compColumn = compSheet.getRange(2, componentColumnIndex, 150, 1);
    var values = compColumn.getValues();
    var backgrounds = compColumn.getBackgrounds();

    var columnData = [];
    var seenNames = new Set();

    for (var j = 0; j < values.length; j++) {
      if (values[j][0] && values[j][0] !== playerName && !seenNames.has(values[j][0])) {
        var cValue = getPlayerPriority(values[j][0], sheet);
        columnData.push({
          name: values[j][0],
          cValue: cValue,
          background: backgrounds[j][0]
        });
        seenNames.add(values[j][0]);
      }
    }

    if (checkboxValue === 0 || checkboxValue === "0") {
      if (!seenNames.has(playerName)) {
        Logger.log("Adding " + playerName + " for missing " + component);
        columnData.push({
          name: playerName,
          cValue: priority || 0,
          background: backgroundColor
        });
      }
    } else if (checkboxValue === 1 || checkboxValue === "1") {
      if (seenNames.has(playerName)) {
        Logger.log("Removing " + playerName + " from " + component);
        columnData = columnData.filter(item => item.name !== playerName);
      }
    }

    columnData.sort((a, b) => b.cValue - a.cValue);
    Logger.log("Column " + componentColumnIndex + " data: " + JSON.stringify(columnData));

    var newValues = Array.from({length: 150}, () => [""]);
    var newBackgrounds = Array.from({length: 150}, () => ["#ffffff"]);
    for (var j = 0; j < columnData.length; j++) {
      newValues[j][0] = columnData[j].name;
      newBackgrounds[j][0] = columnData[j].background;
    }
    compColumn.setValues(newValues);
    compColumn.setBackgrounds(newBackgrounds);
    Logger.log("Updated column " + componentColumnIndex);
  }

  Logger.log("onEdit complete");
}

function removePlayerFromComponents(playerName, spreadsheet) {
  var compSheet = spreadsheet.getSheetByName('Components');
  var compRange = compSheet.getRange(2, 1, 150, 21);
  var values = compRange.getValues();
  var backgrounds = compRange.getBackgrounds();

  for (var col = 0; col < 21; col++) {
    var columnData = [];
    var seenNames = new Set();

    for (var row = 0; row < 150; row++) {
      if (values[row][col] && values[row][col] !== playerName && !seenNames.has(values[row][col])) {
        var cValue = getPlayerPriority(values[row][col], spreadsheet.getSheetByName('Main'));
        columnData.push({
          name: values[row][col],
          cValue: cValue,
          background: backgrounds[row][col]
        });
        seenNames.add(values[row][col]);
      }
    }

    columnData.sort((a, b) => b.cValue - a.cValue);
    Logger.log("Column " + (col + 1) + " data after removing " + playerName + ": " + JSON.stringify(columnData));

    var newValues = Array.from({length: 150}, () => [""]);
    var newBackgrounds = Array.from({length: 150}, () => ["#ffffff"]);
    for (var j = 0; j < columnData.length; j++) {
      newValues[j][0] = columnData[j].name;
      newBackgrounds[j][0] = columnData[j].background;
    }
    compSheet.getRange(2, col + 1, 150, 1).setValues(newValues);
    compSheet.getRange(2, col + 1, 150, 1).setBackgrounds(newBackgrounds);
  }
  Logger.log("Cleared " + playerName + " from all Components columns");
}

function updatePlayerNameInComponents(oldName, newName, mainSheet, spreadsheet) {
  var compSheet = spreadsheet.getSheetByName('Components');
  var compRange = compSheet.getRange(2, 1, 150, 21);
  var values = compRange.getValues();
  var backgrounds = compRange.getBackgrounds();

  var priority = getPlayerPriority(newName, mainSheet);
  var backgroundColor = mainSheet.getRange(mainSheet.getRange(4, 1, 150, 1).createTextFinder(newName).findNext().getRow(), 3).getBackground();

  for (var col = 0; col < 21; col++) {
    var columnData = [];
    var seenNames = new Set();

    for (var row = 0; row < 150; row++) {
      var name = values[row][col];
      if (name) {
        if (name === oldName) {
          if (!seenNames.has(newName)) {
            columnData.push({
              name: newName,
              cValue: priority || 0,
              background: backgroundColor
            });
            seenNames.add(newName);
          }
        } else if (!seenNames.has(name)) {
          var cValue = getPlayerPriority(name, mainSheet);
          columnData.push({
            name: name,
            cValue: cValue,
            background: backgrounds[row][col]
          });
          seenNames.add(name);
        }
      }
    }

    columnData.sort((a, b) => b.cValue - a.cValue);
    Logger.log("Column " + (col + 1) + " data after updating " + oldName + " to " + newName + ": " + JSON.stringify(columnData));

    var newValues = Array.from({length: 150}, () => [""]);
    var newBackgrounds = Array.from({length: 150}, () => ["#ffffff"]);
    for (var j = 0; j < columnData.length; j++) {
      newValues[j][0] = columnData[j].name;
      newBackgrounds[j][0] = columnData[j].background;
    }
    compSheet.getRange(2, col + 1, 150, 1).setValues(newValues);
    compSheet.getRange(2, col + 1, 150, 1).setBackgrounds(newBackgrounds);
  }
  Logger.log("Updated " + oldName + " to " + newName + " in all Components columns");
}

function getPlayerPriority(playerName, mainSheet) {
  var mainData = mainSheet.getRange(4, 1, 150, 3).getValues();
  for (var i = 0; i < mainData.length; i++) {
    if (mainData[i][0] === playerName) {
      return mainData[i][2] || 0; // C value
    }
  }
  return 0;
}
