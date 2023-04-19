const fs = require('fs');
let tokenizer = require('sbd');
const { createCanvas, registerFont } = require('canvas');

// Make sure we got a filename on the command line.
if (process.argv.length < 3) {
  console.log('Usage: node ' + process.argv[1] + ' FILENAME');
  process.exit(1);
}

const filename = process.argv[2];
fs.readFile(filename, 'utf8', async function (err, data) {
  if (err) throw err;

  // generate sentences
  let sentences = generateSentences(data);

  // generate a .png for every paragraph
  for (let i = 0, j = 0; i < sentences.length; i++, j++) {
    let is_title = sentences[i].charAt(0) === '@' ? true : false;
    let txt = '';
    if (is_title) {
      txt = sentences[i].substring(1);
    }
    else{
      let textLength = sentences[i].length, k = 1;
      while (i + k < sentences.length && textLength + sentences[i + k].length <= 500 && sentences[i + k].charAt(0) !== '@') {
        textLength += sentences[i + k].length;
        k++;
      }
      txt = sentences.slice(i, i + k).join(' ');
      i += k - 1;
    }
     await pre_save(txt, j, is_title);
  }
});
  
// Load the font
const fontPath = 'CalibriRegular.ttf';
registerFont(fontPath, { family: 'Calibri' });

// Set the canvas size and margin
const canvasWidth = 1600;
const canvasHeight = 1200;
const margin = 45;

// Set the font size and line height
let fontSize = 60;
let lineHeight = 1.2 * fontSize;

// Create a new canvas and context
const canvas = createCanvas(canvasWidth, canvasHeight);
const context = canvas.getContext('2d');

// Set the text color and font
context.fillStyle = 'white';
context.font = `${fontSize}px Calibri`;
context.textAlign = 'left';
context.textBaseline = 'top';

// Calculate the number of lines and pages
async function pre_save(text, page, is_title){
  let line = '', lines = [];
  const words = text.split(' ');
  for (let j = 0; j < words.length; j++) {
    const testLine = line + words[j] + ' ';
    const testWidth = context.measureText(testLine).width;
    if (testWidth > canvasWidth - 2 * margin) {
      // Push each sub-line to the lines array separately
      line.split('\n').forEach(subLine => {
        lines.push(subLine.trim());
      });
      line = words[j] + ' ';
    } else {
      line = testLine;
    }
  }
  // Push any remaining sub-line to the lines array
  line.split('\n').forEach(subLine => {
    lines.push(subLine.trim());
  });
  if (lines.length > 0) {
    await saveImage(lines, page, is_title);
  }
}

// Save the image
async function saveImage(lines, page, is_title) {
  const imgHeight = margin + lines.length * lineHeight + margin;
  canvas.height = imgHeight;

  // Set the background color to transparent
  context.clearRect(0, 0, canvasWidth, canvasHeight);

  // Draw each line of text
  for (let i = 0; i < lines.length; i++) {
  
    // Set the text color and font
    context.lineWidth = 4;
    context.font = `${fontSize}px Calibri`;
    
    // Draw the text stroke
    context.strokeStyle = 'black';
    context.strokeText(lines[i], margin, margin + (i + 1) * lineHeight);
    
    // Draw the text fill
    context.fillStyle = 'white';
    context.fillText(lines[i], margin, margin + (i + 1) * lineHeight);

    // Add underline to the title
    if(is_title){
        const lineWidth = context.measureText(lines[i]).width;
        const lineX = margin;
        const lineY = margin + (i + 1) * lineHeight + 8; // add some padding between text and underline
        context.strokeStyle = 'blue';
        context.lineWidth = 7;
        context.beginPath();
        context.moveTo(lineX, lineY);
        context.lineTo(lineX + lineWidth, lineY);
        context.stroke();
     }
  }

  // Create a writable stream to write the PNG data to a file
  const fileName = `imgs/img${page}.png`;
  const out = fs.createWriteStream(fileName);

  // Wait for the PNG data to be written to the stream and the file to be saved
  await new Promise((resolve, reject) => {
    out.on('finish', resolve);
    out.on('error', reject);
    canvas.createPNGStream().pipe(out);
  });

  console.log(`Image saved as ${fileName}`);
}


// generate 2-4 randomized sentences per screenshot
function generateSentences(text) {
  let options = {
    newline_boundaries: false,
    html_boundaries: false,
    sanitize: false,
    allowed_tags: false,
    preserve_whitespace: false,
    abbreviations: null,
  };
  let sentences = tokenizer.sentences(text, options);
// remove empty lines
sentences = sentences.filter((line) => line);
let generatedSentences = [];
let currentSentence = '';
for (let i = 0; i < sentences.length; i++) {
let sentence = sentences[i].trim();
if (sentence.charAt(0) === '@') {
// always start a new screenshot for titles
if (currentSentence.length > 0) {
generatedSentences.push(currentSentence);
currentSentence = '';
}
generatedSentences.push(sentence);
} else if (currentSentence.length + sentence.length + 1 <= 500) {
if (currentSentence.length > 0) {
currentSentence += ' ';
}
currentSentence += sentence;
} else {
generatedSentences.push(currentSentence);
currentSentence = sentence;
}
}
if (currentSentence.length > 0) {
generatedSentences.push(currentSentence);
}
return generatedSentences;
}