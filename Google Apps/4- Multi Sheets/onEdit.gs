function onEdit(e) {
  var prop = getSheetProperties(e);

  var triggerColumns = [1, 4, 5, 7, 9, 11]; // A, D, E, G, I, K
  if (prop.sheet.getName() !== 'Main' || prop.range.getRow() < 4 || prop.range.getRow() > 153 || !triggerColumns.includes(prop.range.getColumn())) {
    Logger.log("Edit outside prop.range. Exiting.");
    return;
  }

  var playerName = prop.sheet.getRange(prop.range.getRow(), 1).getValue(); // A
  var oldPlayerName = prop.oldValue; // Previous value before edit
  var column = prop.range.getColumn();

  if (column === 1 && !playerName && oldPlayerName) {
    removePlayerFromComponents(prop, oldPlayerName);
    var row = prop.range.getRow();
    prop.sheet.getRange(row, 4).setValue("None");
    // Logger.log("onEdit complete (name deletion)");
    return;
  }

  if (column === 1 && playerName && oldPlayerName && playerName !== oldPlayerName) {
    updatePlayerNameInComponents(prop, oldPlayerName, playerName);
    // Logger.log("onEdit complete (name change)");
    return;
  }

  var compHeaders = prop.compSheet.getRange(1, 1, 1, 21).getValues()[0]; // A1:U1

  if (column === 4) {
    var oldItem = prop.oldValue;
    if (playerName && oldItem && oldItem.toLowerCase() !== "none") {
      var refData = prop.refSheet.getRange(3, 1, 148, 5).getValues();
      var oldItemRow = refData.find(row => row[0] === oldItem);
      var oldComponents = oldItemRow ? oldItemRow.slice(1, 5).filter(c => c) : [];

      var updates = [];
      for (var j = 0; j < oldComponents.length; j++) {
        var colIndex = compHeaders.indexOf(oldComponents[j]) + 1;
        if (colIndex > 0) {
          var compColumn = prop.compSheet.getRange(2, colIndex, 150, 1);
          var values = compColumn.getValues();
          var backgrounds = compColumn.getBackgrounds();
          var newValues = values.map(row => row[0] === playerName ? [""] : row);
          var newBackgrounds = backgrounds.map((row, idx) => newValues[idx][0] === "" ? ["#ffffff"] : row);

          updates.push({
            range: compColumn,
            values: newValues,
            backgrounds: newBackgrounds
          });
        }
      }

      updates.forEach(update => {
        update.range.setValues(update.values);
        update.range.setBackgrounds(update.backgrounds);
      });

      // Logger.log("Removed " + playerName + " from all relevant columns");
    }
    resetCheckboxes(prop);
  }

  if (!playerName) {
    Logger.log("No player name after checks. Exiting.");
    return;
  }

  var priority = prop.sheet.getRange(prop.range.getRow(), 3).getValue(); // C (1-4)
  var backgroundColor = prop.sheet.getRange(prop.range.getRow(), 3).getBackground(); // C color

  var checkboxValues = [
    prop.sheet.getRange(prop.range.getRow(), 5).getValue(),  // E
    prop.sheet.getRange(prop.range.getRow(), 7).getValue(),  // G
    prop.sheet.getRange(prop.range.getRow(), 9).getValue(),  // I
    prop.sheet.getRange(prop.range.getRow(), 11).getValue()  // K
  ];

  // Check completion and remove from Components
  if ([5, 7, 9, 11].includes(column) && checkboxValues.every(val => val == 1)) {
    var row = prop.range.getRow();
    var itemBeforeReset = prop.sheet.getRange(row, 4).getValue(); // Item before reset

    if (!itemBeforeReset || itemBeforeReset.toLowerCase() === "none") {
      Logger.log("Item already reset to 'none', skipping completion.");
      return;
    }

    var lock = PropertiesService.getScriptProperties().getProperty('editLock');
    if (lock) {
      Logger.log("Script locked from previous completion, exiting.");
      return;
    }

    PropertiesService.getScriptProperties().setProperty('editLock', 'true');

    try {
      var lastRow = prop.completedSheet.getLastRow();
      var completedData = lastRow > 1 ? prop.completedSheet.getRange(2, 1, lastRow - 1, 2).getValues() : [];
      var alreadyLogged = completedData.some(row => row[0] === playerName && row[1] === itemBeforeReset);

      if (alreadyLogged) {
        Logger.log("Completion already logged for " + playerName + " and " + itemBeforeReset + ", skipping.");
        return;
      }

      var refData = prop.refSheet.getRange(3, 1, 148, 5).getValues();
      var completedComponents = [];
      for (var i = 0; i < refData.length; i++) {
        if (refData[i][0] === itemBeforeReset) {
          completedComponents = refData[i].slice(1, 5).filter(c => c);
          break;
        }
      }

      var updates = [];
      for (var j = 0; j < completedComponents.length; j++) {
        var colIndex = compHeaders.indexOf(completedComponents[j]) + 1;
        if (colIndex > 0) {
          var compColumn = prop.compSheet.getRange(2, colIndex, 150, 1);
          var values = compColumn.getValues();
          var backgrounds = compColumn.getBackgrounds();
          var newValues = values.map(row => row[0] === playerName ? [""] : row);
          var newBackgrounds = backgrounds.map((row, idx) => newValues[idx][0] === "" ? ["#ffffff"] : row);

          updates.push({
            range: compColumn,
            values: newValues,
            backgrounds: newBackgrounds
          });
        }
      }

      updates.forEach(update => {
        update.range.setValues(update.values);
        update.range.setBackgrounds(update.backgrounds);
      });

      lastRow = prop.completedSheet.getLastRow();
      completedData = lastRow > 1 ? prop.completedSheet.getRange(2, 1, lastRow - 1, 2).getValues() : [];
      alreadyLogged = completedData.some(row => row[0] === playerName && row[1] === itemBeforeReset);

      if (!alreadyLogged) {
        prop.completedSheet.getRange(lastRow + 1, 1, 1, 2).setValues([[playerName, itemBeforeReset]]);
      }

      prop.sheet.getRange(row, 4, 1, 9).setValues([["None", 0, "", 0, "", 0, "", 0, ""]]);
      // Logger.log("Reset D" + row + " to 'none', cleared E:G:I:K and F:H:J:L");
      // Logger.log("Completion processed, exiting onEdit.");
    } finally {
      PropertiesService.getScriptProperties().deleteProperty('editLock');
      Utilities.sleep(100); // Brief delay to let Sheets catch up
    }
    return;
  }

  var item = prop.sheet.getRange(prop.range.getRow(), 4).getValue(); // D
  // Logger.log("Selected Item: " + item);

  var refData = prop.refSheet.getRange(3, 1, 148, 5).getValues();
  var components = [];
  if (item && item.toLowerCase() !== "none") {
    for (var i = 0; i < refData.length; i++) {
      if (refData[i][0] === item) {
        components = refData[i].slice(1, 5).filter(c => c);
        break;
      }
    }
    prop.sheet.getRange(prop.range.getRow(), 6).setValue(components[2] || "");
    prop.sheet.getRange(prop.range.getRow(), 8).setValue(components[3] || "");
    prop.sheet.getRange(prop.range.getRow(), 10).setValue(components[0] || "");
    prop.sheet.getRange(prop.range.getRow(), 12).setValue(components[1] || "");
    // Logger.log("Updated component labels in F,H,J,L");
  } else {
    // Logger.log("No components fetched (item is none or blank)");
  }

  var checkboxToComponentMap = {
    5: components[2] || "",
    7: components[3] || "",
    9: components[0] || "",
    11: components[1] || ""
  };

  var compHeaders = prop.compSheet.getRange(1, 1, 1, 21).getValues()[0];

  var columnsToCheck = [5, 7, 9, 11];
  for (var i = 0; i < columnsToCheck.length; i++) {
    var col = columnsToCheck[i];
    var component = checkboxToComponentMap[col];
    if (!component) {
      // Logger.log("No component for column " + col);
      continue;
    }

    var checkboxValue = checkboxValues[i];
    var componentColumnIndex = compHeaders.indexOf(component) + 1;

    if (componentColumnIndex === 0) {
      // Logger.log("Component " + component + " not in Components prop.sheet");
      continue;
    }

    var compColumn = prop.compSheet.getRange(2, componentColumnIndex, 150, 1);
    var values = compColumn.getValues();
    var backgrounds = compColumn.getBackgrounds();

    var columnData = [];
    var seenNames = new Set();

    for (var j = 0; j < values.length; j++) {
      if (values[j][0] && values[j][0] !== playerName && !seenNames.has(values[j][0])) {
        var cValue = getPlayerPriority(values[j][0], prop.sheet);
        columnData.push({
          name: values[j][0],
          cValue: cValue,
          background: backgrounds[j][0]
        });
        seenNames.add(values[j][0]);
      }
    }

    if (checkboxValue == 0) {
      if (!seenNames.has(playerName)) {
        columnData.push({
          name: playerName,
          cValue: priority || 0,
          background: backgroundColor
        });
      }
    } else if (checkboxValue === 1 || checkboxValue === "1") {
      if (seenNames.has(playerName)) {
        // Logger.log("Removing " + playerName + " from " + component);
        columnData = columnData.filter(item => item.name !== playerName);
      }
    }

    columnData.sort((a, b) => b.cValue - a.cValue);

    var newValues = Array.from({length: 150}, () => [""]);
    var newBackgrounds = Array.from({length: 150}, () => ["#ffffff"]);
    for (var j = 0; j < columnData.length; j++) {
      newValues[j][0] = columnData[j].name;
      newBackgrounds[j][0] = columnData[j].background;
    }
    compColumn.setValues(newValues);
    compColumn.setBackgrounds(newBackgrounds);
  }

  Logger.log("onEdit complete");
}

