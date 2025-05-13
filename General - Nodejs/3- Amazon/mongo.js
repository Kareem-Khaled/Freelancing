const { MongoClient } = require('mongodb');

const mongoUri = 'mongodb+srv://kemo:123@cluster0.2jeiqrt.mongodb.net/scrapingDB?retryWrites=true&w=majority';
const dbName = 'scrapingDB'; // Replace with your database name
let db;
let client;

const connectToMongo = async () => {
  try {
    client = new MongoClient(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true });
    await client.connect();
    console.log('Connected to MongoDB');
    db = client.db(dbName);
  } catch (err) {
    console.error('Error connecting to MongoDB:', err.message);
    throw err;
  }
};

const insertProduct = async (product) => {
  try {
    const collection = db.collection('products'); 
    const now = new Date();

    await collection.updateOne(
      { asin: product.asin }, 
      {
        $set: {
          ...product,
          updatedAt: now, 
        },
        $setOnInsert: {
          createdAt: now, 
        },
      },
      { upsert: true } 
    );

    // console.log(`Upserted product: ${product.title}`);
  } catch (err) {
    console.error('Error inserting/updating product in MongoDB:', err.message);
  }
};

const isProductWithSamePriceExists = async (asin, price) => {
  try {
    const collection = db.collection('products'); 
    const product = await collection.findOne({ asin, price });

    return product !== null; 
  } catch (err) {
    console.error('Error checking product existence in MongoDB:', err.message);
    throw err;
  }
};

const closeMongoConnection = async () => {
  try {
    if (client) {
      await client.close();
      console.log('MongoDB connection closed');
    }
  } catch (err) {
    console.error('Error closing MongoDB connection:', err.message);
  }
};

const getUniqueAsinCount = async () => {
  try {
    const collection = db.collection('products');
    const uniqueAsins = await collection.distinct('asin'); // Get all unique ASINs
    return uniqueAsins.length; // Return the count of unique ASINs
  } catch (err) {
    console.error('Error getting unique ASIN count from MongoDB:', err.message);
    throw err;
  }
};

// Test the function
if (require.main === module) {
  (async () => {
    try {
      await connectToMongo();
      const uniqueAsinCount = await getUniqueAsinCount();
      console.log(`Number of unique ASINs in the database: ${uniqueAsinCount}`);
      await closeMongoConnection();
    } catch (err) {
      console.error('Error during unique ASIN count test:', err.message);
    }
  })();
}

module.exports = {
  connectToMongo,
  insertProduct,
  closeMongoConnection,
  isProductWithSamePriceExists,
  getUniqueAsinCount, // Export the new function
};