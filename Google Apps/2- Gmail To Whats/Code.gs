// let chatId = '';
// let botId = '';

let gid = "120363218275573972";
let token = "31b33fc998msh9a14c55bdb48c4fp168dbcjsn3ef1d17a2759";
let accounts = [
  "zila@nmz.org.il",
  "candealeng@gmail.com",
  "donotreply_rishuy@oref-rishuy.org.il",
  "yulitz@abubasma.org.il",
  "natanel@nmz.org.il",
  "RZInfo@iplan.gov.il",
  "nomik@land.gov.il",
  "basamat515@gmail.com",
  "ARCHITECT100@gmail.com",
  "mavat_system@iplan.gov.il",
  "Service@iplan.gov.il",
  "klord212@gmail.com"
];

function First_Run(){
  lastRun = new Date();
  PropertiesService.getScriptProperties().setProperty('lastRun', lastRun.getTime());
}

function Check_New_Emails() {
  // Get the user's email address
  // var emailAddress = Session.getActiveUser().getEmail();

  // Get all threads in the inbox
  var threads = GmailApp.getInboxThreads();

  // Access the active sheet
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  // Get the last run timestamp
  var lastRun = PropertiesService.getScriptProperties().getProperty('lastRun') || 0;

  // Loop through threads
  for (var i = 0; i < threads.length; i++) {
    var thread = threads[i];

    // Loop through messages in the thread
    var messages = thread.getMessages();
    var allRead = true;

    for (var j = messages.length - 1; j > -1; j--) {
      var message = messages[j];

      // Check if the message is older than the last run
      if (message.getDate().getTime() <= lastRun) {
        break;
      }

      // Check accounts to send
      var senderEmail = message.getFrom();

      send = false;
      for(let account of accounts){
        if(senderEmail.includes(account)){
          console.log(account);
          send = true;
          break;
        }
      }

      if(!send){
        continue;
      }

      let msg = "- From:\n" + senderEmail + "\n===================\n";

      allRead = false;

      // Extract message content
      var subject = message.getSubject();
      var body = message.getPlainBody();

      msg += "- Subject:\n" + subject + "\n===================\n";
      msg += "- Message:\n" + body + "\n===================\n";
      console.log(msg);

      // Process attachments if any
      var attachments = message.getAttachments();
      for (var k = 0; k < attachments.length; k++) {
        var attachment = attachments[k];

        // Create a folder with the sender's name
        var folder = createFolderIfNotExists(senderEmail);

        var file = folder.createFile(attachment);
        
        // sheet.appendRow([subject, file.getUrl()]);
        console.log(file.getUrl());
        sheet.appendRow([subject, file.getUrl()]);
        if(k == 0){
          msg += "- Files Links:\n";
        }
        msg += file.getUrl() + "\n";

      }
      // Append content to the sheet
      sheet.appendRow([subject, body]);

      Send_To_Whats(msg);

      // Update the last run timestamp with the current message's timestamp
      lastRun = message.getDate().getTime();

      // message.markRead();
    }
    if(allRead){
      break;
    }
  }

  // Update the last run timestamp
  PropertiesService.getScriptProperties().setProperty('lastRun', lastRun);
}

function createFolderIfNotExists(folderName) {
  var rootFolder = DriveApp.getRootFolder();
  var folders = rootFolder.getFoldersByName(folderName);

  if (folders.hasNext()) {
    return folders.next();
  } else {
    return rootFolder.createFolder(folderName);
  }
}

function Send_To_Whats(msg){
  const url = `https://whin2.p.rapidapi.com/send2group?gid=${gid}`;

  const headers = {
    'content-type': 'application/json',
    'X-RapidAPI-Key': token,
    'X-RapidAPI-Host': 'whin2.p.rapidapi.com'
  };

  const payload = {
    text: msg
  };

  const options = {
    method: 'POST',
    headers,
    payload: JSON.stringify(payload),
  };

  const response = UrlFetchApp.fetch(url, options);
  Logger.log(response.getContentText());

  // if (response.getResponseCode() == 200) {
  // }

}






// function Send_Telegram_Message(){
//     let link = `https://api.telegram.org/bot${botId}/sendMessage?chat_id=${chatId}&text=${msg}`;
//     let res = JSON.parse(UrlFetchApp.fetch(link).getContentText());
//     console.log(res);
// }

// function send_Telegram_file(document){

//     // Replace 'Optional' with the caption for the document (can be empty string if not needed)
//     var caption = 'Optional';

//     var payload = {
//       chat_id: chatId,
//       document: document,
//       caption: caption,
//       disable_notification: false,
//       reply_to_message_id: null
//     };

//     var options = {
//       method: 'post',
//       contentType: 'application/json',
//       payload: JSON.stringify(payload)
//     };

//     let link = `https://api.telegram.org/bot${botId}/sendDocument`;
//     let res = JSON.parse(UrlFetchApp.fetch(link, options).getContentText());
//     console.log(res);
// }






