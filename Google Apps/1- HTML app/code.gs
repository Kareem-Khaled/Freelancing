
const doGet = (_) => {
  return HtmlService.createTemplateFromFile('index').evaluate();
}

function Multi(instructors = 99, products = 11) {
  var data = Get_Sheet_Data('multi_data');

  var index = helpMin(data, 1, 1, products);
  if(index == -1) return invalidInput();

  var ret = [["Price Per Year Per Instructor", data[index][4]], 
             ["Total", data[index][4] * instructors]];

  return formatData(ret);
}

function Sticky(instructors = 255) {
  var data = Get_Sheet_Data('sticky_data');

  var index = helpMin(data, 1, 2, instructors);
  if(index == -1) return invalidInput();

  var ret = [["Price per Instructor", data[index][5]], 
            ["Total", data[index][5] * instructors]];

  console.log(formatData(ret));
  return formatData(ret);
}

function Site(instructors = 84323) {
  var data = Get_Sheet_Data('site_data');

  var index = helpMin(data, 1, 2, instructors);
  if(index == -1) return invalidInput();

  var ret = [["Tier",	"1-Year",	"2-Year",	"3-Year"]];
  ret.push(helpCalc(data, index, 4, 6, [1]));
  ret.push(helpCalc([ret[1]], 0, 0, 2, [instructors]));
  ret.push(helpCalc([ret[2]], 0, 0, 2, [1, 2, 3]));

  ret[1] = ["Price per Instructor"].concat(...ret[1]);
  ret[2] = ["Total per Year"].concat(...ret[2]);
  ret[3] = ["Total License Cost"].concat(...ret[3]);

  return formatData(ret);
}


function helpCalc(data, row, l, r, val){
  var ret = [];
  for(var i = l; i <= r; i++){
    var current = data[row][i] * val[Math.min(i, val.length - 1)];
    ret.push(current);
  }
  return ret;
}

function helpMin(data, min, max, instructors){
  var index = -1;
  for(var i = 1; i < data.length; i++){ // Min -- Max
    if(instructors >= data[i][min] && instructors <= data[i][max]){
      index = i; 
      break;
    }
  }
  return index;
}

function Get_Sheet_Data(name){
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(name).getDataRange().getValues();
}


function processForm(option, instructors, products) {
  if(option == "site") return Site(instructors);
  if(option == "sticky") return Sticky(instructors);
  return Multi(instructors, products);
}



function formatData(data){
  for(var i = 0; i < data.length; i++){
    for(var j = 0; j < data[0].length; j++){
        if (typeof data[i][j] === 'string') continue;
        data[i][j] = new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD'
        }).format(data[i][j]);
    }
  }
  return data;
}

function invalidInput(){
  return [["Invalid Input, Please Try again"]];
}


