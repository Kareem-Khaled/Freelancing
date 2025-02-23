function TransferFilesAccess() {
  var ui = SpreadsheetApp.getUi();
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = sheet.getRange("A1:B1").getValues();
  
  var sourceEmail = data[0][0];
  var targetEmail = data[0][1];

  if (!sourceEmail || !targetEmail) {
    ui.alert("Error", "Please enter both emails in A1 (source) and B1 (target).", ui.ButtonSet.OK);
    return;
  }

  var files = getSharedFilesFaster(sourceEmail);
  if (files.length === 0) {
    ui.alert("No Files Found", "No files shared with " + sourceEmail, ui.ButtonSet.OK);
    return;
  }  

  files.forEach(file => {
    try {
      var driveFile = DriveApp.getFileById(file.Id);
      var currentAccess = getCurrentAccess(driveFile, sourceEmail);
      
      if (currentAccess) {
        if (currentAccess === "writer") {
          driveFile.addEditor(targetEmail);
        } else {
          driveFile.addViewer(targetEmail);
        }
        
        Logger.log("Access granted: " + file.Name + " (" + currentAccess + ")");
      }
    } catch (error) {
      Logger.log("Error updating access for: " + file.Name + " - " + error);
    }
  });

  ui.alert("Process Complete", "Access successfully transferred!", ui.ButtonSet.OK);
}

function getSharedFilesFaster(targetEmail) {
  var query = `'${targetEmail}' in readers or '${targetEmail}' in writers`;
  var files = [];
  var pageToken = null;

  do {
    var response = Drive.Files.list({
      q: query,
      fields: "files(id, name, mimeType, modifiedTime, webViewLink, permissions)",
      pageSize: 100,
      pageToken: pageToken
    });

    if (response.files && response.files.length > 0) {
      response.files.forEach(file => {
        files.push({
          Id: file.id,
          Name: file.name,
          URL: file.webViewLink,
          Permissions: file.permissions
        });
      });
    }

    pageToken = response.nextPageToken;
  } while (pageToken);
  
  return files;
}

function getCurrentAccess(file, sourceEmail) {
  var editors = file.getEditors().map(user => user.getEmail());
  var viewers = file.getViewers().map(user => user.getEmail());

  if (editors.includes(sourceEmail)) return "writer";
  if (viewers.includes(sourceEmail)) return "reader";
  return null;
}
