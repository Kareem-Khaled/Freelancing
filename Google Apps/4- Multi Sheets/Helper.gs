function getSheetProperties(e) {
  var source = e.source;
  var range = e.range;
  var oldValue = e.oldValue;
  var sheet = source.getSheetByName('Main');
  var refSheet = source.getSheetByName('Reference');
  var compSheet = source.getSheetByName('Components');
  var completedSheet = source.getSheetByName('Completed');
  
  return {
    sheet,
    range,
    oldValue,
    source,
    refSheet,
    compSheet,
    completedSheet,
  };
}

function removePlayerFromComponents(prop, playerName) {
  var compSheet = prop.compSheet;
  var compRange = compSheet.getRange(2, 1, 150, 21);
  var values = compRange.getValues();
  var backgrounds = compRange.getBackgrounds();

  var newValues = Array.from({ length: 150 }, () => Array(21).fill(""));
  var newBackgrounds = Array.from({ length: 150 }, () => Array(21).fill("#ffffff"));

  for (var col = 0; col < 21; col++) {
    var columnData = [];
    var seenNames = new Set();

    for (var row = 0; row < 150; row++) {
      if (values[row][col] && values[row][col] !== playerName && !seenNames.has(values[row][col])) {
        var cValue = getPlayerPriority(values[row][col], prop.sheet);
        columnData.push({
          name: values[row][col],
          cValue: cValue,
          background: backgrounds[row][col]
        });
        seenNames.add(values[row][col]);
      }
    }

    columnData.sort((a, b) => b.cValue - a.cValue);

    for (var j = 0; j < columnData.length; j++) {
      newValues[j][col] = columnData[j].name;
      newBackgrounds[j][col] = columnData[j].background;
    }
  }

  compSheet.getRange(2, 1, 150, 21).setValues(newValues);
  compSheet.getRange(2, 1, 150, 21).setBackgrounds(newBackgrounds);

  // Logger.log("Cleared " + playerName + " from all Components columns");
}

function updatePlayerNameInComponents(prop, oldName, newName) {
  var compSheet = prop.compSheet;
  var compRange = compSheet.getRange(2, 1, 150, 21);
  var values = compRange.getValues();
  var backgrounds = compRange.getBackgrounds();

  var priority = getPlayerPriority(newName, prop.sheet);
  var newNameRow = prop.sheet.getRange(4, 1, 150, 1).createTextFinder(newName).findNext();
  var backgroundColor = newNameRow ? prop.sheet.getRange(newNameRow.getRow(), 3).getBackground() : "#ffffff";

  var newValues = Array.from({ length: 150 }, () => Array(21).fill(""));
  var newBackgrounds = Array.from({ length: 150 }, () => Array(21).fill("#ffffff"));

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

    for (var j = 0; j < columnData.length; j++) {
      newValues[j][col] = columnData[j].name;
      newBackgrounds[j][col] = columnData[j].background;
    }
  }

  compSheet.getRange(2, 1, 150, 21).setValues(newValues);
  compSheet.getRange(2, 1, 150, 21).setBackgrounds(newBackgrounds);

  // Logger.log("Updated " + oldName + " to " + newName + " in all Components columns");
}

var cachedMainDataMap = null;
function getPlayerPriority(playerName, mainSheet) {
  if (!cachedMainDataMap) {
    var mainData = mainSheet.getRange(4, 1, 150, 3).getValues();
    cachedMainDataMap = {};
    for (var i = 0; i < mainData.length; i++) {
      cachedMainDataMap[mainData[i][0]] = mainData[i][2] || 0;
    }
  }
  return cachedMainDataMap[playerName] || 0;
}

function resetCheckboxes(prop) {
  prop.sheet.getRange(prop.range.getRow(), 5, 1, 8).setValues([[0, "", 0, "", 0, "", 0, ""]]);
  // Logger.log("Reset checkboxes E,G,I,K to 0 and cleared labels F,H,J,L");
}





