const WebSocket = require('ws');
const name = process.argv[2] || 'Kemo';

const ws = new WebSocket('ws://localhost:8080/');

ws.on('open', () => {
  console.log('Connected to the server');

  // Send a message with the client's name as a property
  // ws.send(JSON.stringify({ name, message: 'Hello from the client!' }));
 
  // Uncomment the next line to get the online clients
  // ws.send(JSON.stringify({ onlineClients: true }));

  // Sending the username as a string
  ws.send(`user: ${name}`)
});

ws.on('message', (message) => {
  const data = JSON.parse(message);
  if(data.message){
    console.log(`Received message: ${data.message}`);
  }
  if(data.onlineClients){
    console.log(`Online Clients: ${JSON.stringify(data.onlineClients)}`);
  }
});
