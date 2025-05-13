// const axios = require('axios');
const cheerio = require('cheerio');
const rp = require('request-promise');
const _ = require('lodash');
const fs = require('fs-extra');
const userAgent = require('random-useragent');
const config = require('./config');

// const proxies = fs.readFileSync('proxies.txt', 'utf-8').split('\n').map(line => line.trim());

// function getRandomProxy() {
//   const randomIndex = Math.floor(Math.random() * proxies.length);
//   return proxies[randomIndex];
// }

class AmazonEgyptScraper {
  constructor() {
    // this.requestQueue = [];
    // this.activeRequests = 0;
    // this.requestHistory = [];
  }

  async makeRequest(url) {
    // if (this.activeRequests >= config.maxConcurrentRequests) {
    //   await new Promise(resolve => this.requestQueue.push(resolve));
    // }
  
    let attempt = 0;
  
    while (attempt <= config.maxRetries) {
      // this.activeRequests++;
  
      try {
        // await this.randomDelay(config.requestDelay, config.requestDelay * 2);
        // const proxy = getRandomProxy();
        // const [host, port, username, password] = proxy.split(':');
        // const proxyUrl = `http://${username}:${password}@${host}:${port}`;
  
        const headers = {
          // "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
          'User-Agent': userAgent.getRandom(),
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
          'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
          'Referer': config.baseUrl,
          // 'Cookie': 'session-id=260-4187046-9196906; i18n-prefs=EGP; ubid-acbeg=259-7011251-0201911; lc-acbeg=en_AE; session-id-time=2082787201l; session-token=vfOErBFF9EEb5+ao1te+G1ZwGb0SPQ0TF/4pualX4+rKP6XLvu/iTIHIInhWqTgZ3l95nTBLiCBubP1DMcVMD1H5oaXitX4K5f4jQzVpy0BXrOWb5LJegKuH3f8kXkG1EUkmb4XXd8ATQ81fsjjzgsEoHCdQatsh6lRKbe6GNDmPffOLDY46D9WSk0w5fu9btsvgoTcSfufYQZU9RzBdp1J5EYgweYE40oRphAFqjfABc1v3Nq3XN22KBokaDtHvXc0m4er8uV/e72mpzl9T76OXFdq5PiCuquA5SP4q+MY3AXMppOos8YkkEG/VAHLsfz36VpC0cHNi9EPFgMXK4fTmO4DLRhKm; csm-hit=tb:4BP6A1XWQNEQYP7950J8+s-NS7ARF314QVEC67Q3TW9|1745591471771&t:1745591471771&adb:adblk_no'
        };
  
        const options = {
          uri: url,
          method: 'GET',
          // proxy: proxyUrl,
          headers: headers
        };
  
        const response = await rp(options);
  
        // const encodedUrl = encodeURIComponent(url);
        // const crawlbaseUrl = `https://api.crawlbase.com/?token=${config.token}&url=${encodedUrl}`;
        // const response = await (await axios.get(crawlbaseUrl)).data;
  
        // this.requestHistory.push({ url, timestamp: new Date() });
  
        // this.activeRequests--;
        // if (this.requestQueue.length > 0) this.requestQueue.shift()();
  
        return response;
      } catch (error) {
        // this.activeRequests--;
        // if (this.requestQueue.length > 0) this.requestQueue.shift()();
  
        if (attempt < config.maxRetries) {
          console.log(`Retrying ${url} (${attempt + 1}/${config.maxRetries})`);
          attempt++;
          await this.Delay();
          continue;
        } else {
          throw new Error(`Request failed: ${error.message}`);
        }
      }
    }
  }
  

  async Delay() {
    const delay = _.random(config.minDelay, config.maxDelay);
    return new Promise(resolve => setTimeout(resolve, delay));
  }

  extractASIN(url) {
    const match = url.match(/\/dp\/([A-Z0-9]{10})/);
    return match ? match[1] : null;
  }

  async getLastPageNumber(html, url) {
    let attempt = 0;
  
    while (attempt <= config.maxRetries) {
      const $ = cheerio.load(html);
  
      const nextButton = $('.s-pagination-next').first();
      let previousItem = nextButton.closest('li').prev();
      if(previousItem.length === 0) {
        previousItem = nextButton.closest('span').prev();
      }
      let lastPageText = previousItem.text().trim();
  
      if (!/^\d+$/.test(lastPageText)) {
        const allPageNumbers = [];
  
        $('.s-pagination-item').each((i, el) => {
          const text = $(el).text().trim();
          if (/^\d+$/.test(text)) {
            allPageNumbers.push(parseInt(text));
          }
        });
  
        if (allPageNumbers.length > 0) {
          lastPageText = Math.max(...allPageNumbers);
        } else {
          lastPageText = 1;
        }
      }
  
      const lastPage = parseInt(lastPageText);
  
      if (lastPage !== 1 || attempt === config.maxRetries) {
        return lastPage;
      }
  
      attempt++;
      console.log(`Retrying getLastPageNumber for ${url} (${attempt}/${config.maxRetries})`);
      await this.Delay();
      html = await this.makeRequest(url);
    }
  
    return 1;
  }
}

module.exports = AmazonEgyptScraper;
