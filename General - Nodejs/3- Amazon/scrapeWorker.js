const { parentPort, workerData, isMainThread } = require('worker_threads');
const cheerio = require('cheerio');
const AmazonEgyptScraper = require('./scraper');
const scraper = new AmazonEgyptScraper();
const config = require('./config');

// Validate we're in a worker thread
if (isMainThread) {
  throw new Error('This script must run as a worker thread');
}

// Memory-efficient HTML processing
function processHtml(html, url) {
  const $ = cheerio.load(html, {
    decodeEntities: true,
    lowerCaseTags: true,
    lowerCaseAttributeNames: true,
    recognizeSelfClosing: true,
  });

  const product = {};
  
  // Extract promo information
  const promoLabel = $('label[id^="greenBadge"]').first().text().trim();
  const promoMessage = $('span[id^="promoMessage"]').first().text().trim();
  product.code = promoLabel ? `${promoLabel} ${promoMessage}`.split("Terms")[0].trim() : "";

  // Extract price information
  // const rawPrice = $('.a-price .a-offscreen').first().text().trim().replace(/[^\d.]/g, '');
  // if (rawPrice) {
  //   product.price = rawPrice;
  // }

  // Additional product details if needed
  // product.asin = scraper.extractASIN(url);
  // product.url = url;

  return product;
}

async function scrapeProduct(url) {
  let attempt = 0;
  const product = {};

  while (attempt < config.maxRetries) {
    try {
      const response = await scraper.makeRequest(url);
      const result = processHtml(response, url);

      // If we got both price and code, we're done
      // result.price && result.code
      if (result.code) {
        Object.assign(product, result);
        break;
      }

      // Otherwise merge what we got and try again
      Object.assign(product, result);

    } catch (error) {
      console.error(`Attempt ${attempt + 1} failed for ${url}:, error.message`);
    } 
      attempt++;
  }

  return product;
}

// Handle messages from main thread
parentPort.on('message', async (message) => {
  try {
    if (message.url) {
      const result = await scrapeProduct(message.url);
      parentPort.postMessage(result);
    } else if (message === 'terminate') {
      // Cleanup resources if needed
      process.exit(0);
    }
  } catch (error) {
    console.error('Worker error:', error);
    parentPort.postMessage({ error: error.message });
  }
});

// Handle initial workerData if provided
if (workerData?.url) {
  scrapeProduct(workerData.url)
    .then(result => parentPort.postMessage(result))
    .catch(error => {
      console.error('Initial worker error:', error);
      parentPort.postMessage({ error: error.message });
    });
}