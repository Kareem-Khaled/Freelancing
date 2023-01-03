const fs = require('fs');
const WebSocket = require('ws');
const crypto = require('crypto');
const wsServer = new WebSocket.Server({ port: 8080 });

// Global object to store clients names
const clients = {};
let idCounter = 0;

// Generate names
function generateRandomName() {
  return crypto.randomBytes(8).toString('hex');
}

// Writing the data into the file
const updateData = () => {
  const clientList = Object.entries(clients).map(([id, name]) => `${id}: ${name}`).join('\n');
  fs.writeFileSync('clients.txt', clientList);
}

wsServer.on('connection', (ws) => {
  console.log('New connection');

  // Sending a message to the client
  ws.send(JSON.stringify({ onlineClients: clients, message: 'Welcome to our server' }));
  
  // Generate a unique ID for the client
  const id = idCounter++;
  
  // Generate a random name for the client
  clients[id] = generateRandomName();
  updateData();

  // Wait for the client to send a message
  ws.on('message', (message) => {
    try {
        // Parse the message as JSON
        const data = JSON.parse(message);
        
        // Check if the message has a "name" property
        if (data.name) {
          // Store the client's name in the global object
          clients[id] = data.name;
          console.log(`Received name for id: ${id}, name: ${data.name}`);
          updateData();
        }
        
        if(data.message){
          console.log(`Received message: ${data.message}`);
        }

        if(data.onlineClients){
          ws.send(JSON.stringify({ onlineClients: clients, message: 'Here are the online clients' }));
        }
    } catch (error) {
        message = message.toString();
        if(message.includes('user:')){
          let username = message.split(': ')[1];
          clients[id] = username;
          console.log(`Received name for id: ${id}, name: ${username}`);
          updateData();
        }
        else{
          console.log(`Received message: ${message}`);
        }
    }
  });

  // Remove the client's name from the global object when the connection is closed
  ws.on('close', () => {
    console.log(`Disconnection id: ${id}, name: ${clients[id]}`);
    delete clients[id];
    updateData();
  });
});

console.log('WebSocket server listening on port 8080');