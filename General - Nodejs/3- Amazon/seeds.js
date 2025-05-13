const fs = require('fs');
const path = require('path');
const AmazonEgyptScraper = require('./scraper');
const scraper = new AmazonEgyptScraper();
const cheerio = require('cheerio');

const BASE_URL = 'https://www.amazon.eg';

async function scrapeFirstLevelSubcategories(url) {
  const html = await scraper.makeRequest(url);
  const $ = cheerio.load(html);

  // Extract the root category name (usually in <h1> or <span class="a-size-base a-text-bold">)
  let rootName = $('h1').first().text().trim();
  if (!rootName) {
    rootName = $('span.a-size-base.a-text-bold').first().text().trim();
  }

  let items = $('li.s-navigation-indent-2');
  if (items.length === 0)
    items = $('li.apb-browse-refinements-indent-2');

  const subcategories = [];

  for (let i = 0; i < items.length; i++) {
    const $el = $(items[i]);
    const name = $el.find('a span').text().trim();
    const href = $el.find('a').attr('href');
    //  + '&p_n_deal_type=26901036031'
    const fullUrl = href ? BASE_URL + href + '&fs=true' + '&p_6=A1ZVRGNO5AYLOV' : null;

    if (!name || !fullUrl) continue;

    console.log(`🔹 ${name}`);

    subcategories.push({
      name,
      url: fullUrl,
    });
  }

  return { rootName, subcategories };
}

async function startScraping() {
  const rootUrl = 'https://www.amazon.eg/-/en/%D8%A5%D9%84%D9%83%D8%AA%D8%B1%D9%88%D9%86%D9%8A%D8%A7%D8%AA/b/?ie=UTF8&node=18018102031&ref_=nav_cs_electronics';
  // const rootUrl = 'https://www.amazon.eg/-/en/%D8%A3%D9%84%D8%B9%D8%A7%D8%A8-%D8%A7%D9%84%D9%81%D9%8A%D8%AF%D9%8A%D9%88/b/?ie=UTF8&node=18022560031&ref_=nav_cs_videogames';

  const { rootName, subcategories } = await scrapeFirstLevelSubcategories(rootUrl);

  const root = {
    name: rootName || 'Unknown Category',
    url: rootUrl,
    children: subcategories,
  };

  const filePath = path.join(__dirname, 'categories.json');
  fs.writeFileSync(filePath, JSON.stringify(root, null, 2), 'utf-8');
  console.log(`✅ First-level categories saved to ${filePath}`);
}

startScraping();
