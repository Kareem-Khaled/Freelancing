const os = require('os');
const fs = require('fs');
const path = require('path');
const async = require('async');
const cheerio = require('cheerio');
const { Mutex } = require('async-mutex');
const { Worker } = require('worker_threads');
const { app, BrowserWindow, ipcMain } = require('electron');
const { connectToMongo, insertProduct, closeMongoConnection, isProductWithSamePriceExists } = require('./mongo');

const AmazonEgyptScraper = require('./scraper');
const scraper = new AmazonEgyptScraper();

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(createWindow);

ipcMain.handle('scrape', async (event, {
  urls,
  fetchThreads = 5,
  scrapeThreads = 5,
  // workers = 5,
  // bufferLimit = 1000
}) => {
  await connectToMongo();
  const startTime = Date.now();
  let scrapeProducts = 0;
  // let bufferFileIndex = 1;
  // const productLock = new Mutex();
  // const exeDir = path.dirname(app.getPath('exe')).split("node_modules")[0];
  // console.log(exeDir);
  // return {
  //   success: true,
  //   scrapeProducts: 0,
  //   timing: {
  //     startTime: 0,
  //     endTime: 0,
  //     duration: 0
  //   },
  //   msg: exeDir
  // };

  // Use stream-based writing to avoid memory buildup
  // const createWriteStream = (index) => {
  //   const filePath = path.join(exeDir, `output-part-${index}.json`);
  //   const writeStream = fs.createWriteStream(filePath, { flags: 'w' });
  //   writeStream.write('[\n');
  //   return { stream: writeStream, filePath, firstItem: true };
  // };

  // let currentStream = createWriteStream(bufferFileIndex++);

  const writeProduct = async (product) => {
    await insertProduct(product);
    scrapeProducts++;
    event.sender.send('update-scraped-count', scrapeProducts);
  };

  // Worker pool for product scraping
  class WorkerPool {
    constructor() {
      // this.size = size;
      this.size = Math.max(1, os.cpus().length - 1);
      this.workers = [];
      this.taskQueue = [];
      this.initialize();
    }

    initialize() {
      for (let i = 0; i < this.size; i++) {
        const worker = new Worker(path.join(__dirname, 'scrapeWorker.js'));
        // console.log(`Worker ${i + 1} created.`); // Log worker creation
    
        worker.on('message', (result) => {
          const taskItem = this.taskQueue.shift();
          if (taskItem) {
            taskItem.resolve(result);
          }
          this.processQueue();
        });
    
        worker.on('error', (err) => {
          const taskItem = this.taskQueue.shift();
          if (taskItem) {
            taskItem.reject(err);
          }
          console.error(`Worker ${i + 1} encountered an error:`, err); // Log worker error
          this.processQueue();
        });
    
        this.workers.push({ worker, busy: false });
      }
    }

    processQueue() {
      // console.log('Task queue length:', this.taskQueue.length); // Log the number of tasks in the queue
      // console.log('Available workers:', this.workers.filter(w => !w.busy).length); // Log the number of free workers
    
      if (this.taskQueue.length === 0) return;
    
      const availableWorker = this.workers.find(w => !w.busy);
      if (!availableWorker) {
        // console.log('No available workers at the moment.');
        return;
      }
    
      const taskItem = this.taskQueue.shift();
      if (!taskItem) {
        // console.log('No task item found in the queue.');
        return;
      }
    
      const { task, resolve, reject } = taskItem;
    
      // console.log('Assigning task to worker:', task);
    
      const handleMessage = (result) => {
        // console.log('Task completed by worker:', result);
        availableWorker.worker.off('message', handleMessage);
        availableWorker.worker.off('error', handleError);
        availableWorker.busy = false;
        resolve(result);
        this.processQueue();
      };
    
      const handleError = (err) => {
        // console.error('Task failed with error:', err);
        availableWorker.worker.off('message', handleMessage);
        availableWorker.worker.off('error', handleError);
        availableWorker.busy = false;
        reject(err);
        this.processQueue();
      };
    
      availableWorker.worker.once('message', handleMessage);
      availableWorker.worker.once('error', handleError);
    
      availableWorker.busy = true;
      availableWorker.worker.postMessage(task);
    }
    
    runTask(task) {
      return new Promise((resolve, reject) => {
        this.taskQueue.push({ task, resolve, reject });
        this.processQueue();
      });
    }

    async terminate() {
      await Promise.all(this.workers.map(({ worker }, index) => 
        new Promise(resolve => {
          worker.terminate().then(() => {
            // console.log(`Worker ${index + 1} terminated.`);
            resolve();
          }).catch(err => {
            console.error(`Failed to terminate Worker ${index + 1}:`, err);
            resolve();
          });
        })
      ));
    }
  }

  const workerPool = new WorkerPool();

  const processPage = async (html, page) => {
    const $ = cheerio.load(html);
    const productElements = $('[data-component-type="s-search-result"]');
    const products = [];

    for (const el of productElements) {
      try {
        const url = 'https://www.amazon.eg' + $(el).find('a.a-link-normal.s-no-outline').attr('href');
        const title = $(el).find('a h2 span').text().trim();
        const priceText = $(el).find('.a-price .a-offscreen').first().text().trim().replace(/[^\d.]/g, '');
        const oldPriceText = $(el).find('.a-price[data-a-color="secondary"] .a-offscreen').first().text().trim().replace(/[^\d.]/g, '');

        const price = parseFloat(priceText);
        const oldPrice = parseFloat(oldPriceText);
        const discount = oldPrice ? (Math.ceil(((oldPrice - price) / oldPrice) * 100)) + '%' : '0.00%';

        const discountText = $(el).find('[data-cy="price-recipe"] .a-row.a-size-base.a-color-secondary span').text().trim();

        let product = {
          title,
          price: priceText || null,
          oldPrice: oldPriceText || null,
          discount,
          asin: scraper.extractASIN(url),
          image: $(el).find('img.s-image').attr('src'),
          url
        };
        if(!priceText.length) product.price = "Currently unavailable";
        
        if (discountText.includes('% off')) {
          // if (!priceText.length) console.log(`Product ${product.asin} ..... ${priceText}`);
            // console.log(`Scraping product ${product.asin}...`);
            const productDetails = await workerPool.runTask({ url });
            if (productDetails) {
              product = { ...product, ...productDetails };
              if (!exists) {
                await writeProduct(product);
                products.push(product);
              }            
              products.push(product);
          }
        } else {
          const exists = await isProductWithSamePriceExists(product.asin, product.price);
          if (!exists) {
            await writeProduct(product);
            products.push(product);
          }
        }
      } catch (err) {
        console.error('Error processing product:', err.message);
      }
    }

    return products;
  };

  const fetchQueue = async.queue(async (task, done) => {
    try {
      // console.log(`Fetching page ${task.page}...`);
      const html = await scraper.makeRequest(task.url);
      scrapeQueue.push({ html, page: task.page });
    } catch (err) {
      console.error(`Failed to fetch page ${task.page}:`, err.message);
    } finally {
      done();
    }
  }, fetchThreads);

  const scrapeQueue = async.queue(async (task, done) => {
    try {
      // console.log(`Scraping page ${task.page}...`);
      await processPage(task.html, task.page);
    } catch (err) {
      console.error(`Scraping failed on page ${task.page}`, err.message);
    } finally {
      done();
    }
  }, scrapeThreads);

  const lastPageQueue = async.queue(async (url, done) => {
    try {
      const html = await scraper.makeRequest(url);
      const lastPage = await scraper.getLastPageNumber(html, url);
      // console.log(`Scraping ${lastPage}...`);
      console.log(`Last page number for ${url}: ${lastPage}`);
      for (let pageNum = 1; pageNum <= lastPage; pageNum++) {
        const pageUrl = `${url}&page=${pageNum}`;
        fetchQueue.push({ url: pageUrl, page: pageNum });
      }
    } catch (err) {
      console.error(`Failed to get last page for ${url}:`, err.message);
    } finally {
      done();
    }
  }, 5);

  return new Promise(async (resolve) => {
    try {
      lastPageQueue.push(urls);

      lastPageQueue.drain(() => {
        // console.log('Last page fetching completed, starting to fetch pages...');
        fetchQueue.drain(() => {
          // console.log('All pages fetched.');
          scrapeQueue.drain(async () => {
            // console.log('Scraping completed.');
            // Finalize the current stream
            // await new Promise(resolve => {
            //   currentStream.stream.end('\n]', 'utf-8', () => {
            //     console.log(`- Final chunk saved to ${currentStream.filePath}`);
            //     resolve();
            //   });
            // });

            // Clean up worker pool
            await workerPool.terminate();
            await closeMongoConnection();

            const endTime = Date.now();
            resolve({
              success: true,
              scrapeProducts,
              timing: {
                startTime: new Date(startTime).toISOString(),
                endTime: new Date(endTime).toISOString(),
                duration: ((endTime - startTime) / 1000).toFixed(2)
              }
            });
          });
        });
      });
    } catch (err) {
      console.error('Scraping error:', err);
      resolve({ success: false, error: err.message });
    }
  });
});