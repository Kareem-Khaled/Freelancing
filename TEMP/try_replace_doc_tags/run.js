const { Document } = require('docxtemplater');
const fs = require('fs');
const path = require('path');

// Load the .docx file template
const templatePath = path.join(__dirname, 'document.docx');
const content = fs.readFileSync(templatePath, 'binary');

// Create a new instance of the Document
const doc = new Document();

// Load the template content
doc.load(content);

// Define the tag-value mappings
const tagValueMappings = {
  tag1: 'value1',
  tag2: 'value2',
};

// Replace the tags with new values
doc.setData(tagValueMappings);
doc.render();

// Save the updated .docx file
const outputPath = path.join(__dirname, 'output.docx');
const updatedContent = doc.getZip().generate({ type: 'nodebuffer' });
fs.writeFileSync(outputPath, updatedContent);

console.log('File saved:', outputPath);
