//jshint esversion:8

import puppeteer from "puppeteer";
import config from "./config.js";
import fs from "fs";
import xlsx from "xlsx";
import { images } from "images-downloader";

let browser;

const headers = [
  "product_name",
  "description",
  "style_number",
  "brand",
  "category",
  "product_url",
  "img",
  "local_image",
  "color",
  "size",
  "price",
  "warehouse1",
  "warehouse2",
];
const headers2 = [
  "product_name",
  "style_number",
  "brand",
  "category",
  "color",
  "size",
  "price",
  "warehouse1",
  "warehouse2",
];

if (!fs.existsSync("./data")) {
  fs.mkdirSync("./data");
}

if (!fs.existsSync("./data/xlsx")) {
  fs.mkdirSync("./data/xlsx");
}
if (!fs.existsSync("./data/xlsx/full")) {
  fs.mkdirSync("./data/xlsx/full");
}
if (!fs.existsSync("./data/xlsx/min")) {
  fs.mkdirSync("./data/xlsx/min");
}

if (!fs.existsSync("./data/images")) {
  fs.mkdirSync("./data/images");
}

function saveToSheet_full(data, fileName) {
  fileName = fileName.replace('<folder>', 'full');
  const full_data = data.map((e) => {
    const obj = {};
    for (let h of headers) {
      obj[h] = e[h] || "";
    }
    return obj;
  });

  let workbook, worksheet;
  try {
    workbook = xlsx.readFile(fileName);
    worksheet = workbook.Sheets[workbook.SheetNames[0]];
  } catch (error) {
    if (error.code === 'ENOENT') {
      workbook = xlsx.utils.book_new();
      worksheet = xlsx.utils.json_to_sheet([]);
    } else {
      throw error;
    }
  }

  const existingData = xlsx.utils.sheet_to_json(worksheet);
  const updatedData = existingData.concat(full_data);
  const updatedWorksheet = xlsx.utils.json_to_sheet(updatedData);
  const updatedWorkbook = xlsx.utils.book_new();

  xlsx.utils.book_append_sheet(updatedWorkbook, updatedWorksheet, 'product');
  xlsx.writeFile(updatedWorkbook, fileName);
}

function saveToSheet_min(data, fileName) {
  fileName = fileName.replace('<folder>', 'min');
  const full_data = data.map((e) => {
    const obj = {};
    for (let h of headers2) {
      obj[h] = e[h] || "";
    }
    return obj;
  });

  let workbook, worksheet;
  try {
    workbook = xlsx.readFile(fileName);
    worksheet = workbook.Sheets[workbook.SheetNames[0]];
  } catch (error) {
    if (error.code === 'ENOENT') {
      workbook = xlsx.utils.book_new();
      worksheet = xlsx.utils.json_to_sheet([]);
    } else {
      throw error;
    }
  }

  const existingData = xlsx.utils.sheet_to_json(worksheet);
  const updatedData = existingData.concat(full_data);
  const updatedWorksheet = xlsx.utils.json_to_sheet(updatedData);
  const updatedWorkbook = xlsx.utils.book_new();

  xlsx.utils.book_append_sheet(updatedWorkbook, updatedWorksheet, 'product');
  xlsx.writeFile(updatedWorkbook, fileName);
}

function scrape() {
  const selector = {
    product_name: ".product-info .product-title",
    description: "#tab-description p",
    category: "span.posted_in > a[rel='tag']",
    row: "div[role='rowgroup'][data-attributes]",
    img: "img",
    color:"div[role='rowgroup'][data-attributes]  > [role='cell']:nth-child(2) span",
    size: "div[role='rowgroup'][data-attributes]  > [role='cell']:nth-child(3) span",
    price: "div[role='rowgroup'][data-attributes]  > [role='cell']:nth-child(4) span",
    warehouse1: "div[role='rowgroup'][data-attributes]  > [role='cell']:nth-child(5) span.kati-sportcap-variations-table__warehouse-quantity",
    warehouse2: "div[role='rowgroup'][data-attributes]  > [role='cell']:nth-child(6) span.kati-sportcap-variations-table__warehouse-quantity",
  };

  function stringPrettify(str) {
    try {
      return str.replace(/\\n|  /gi, "").trim();
    }
    catch {
      return str;
    }
    //.toLowerCase();
  }

  const data = {};
  data["product_name"] = stringPrettify(
    document.querySelector(selector.product_name)?.textContent || ' '
  );
  data["style_number"] = stringPrettify(
    document.querySelector(selector.product_name)?.textContent || ' '
  ).split(" ")[0];
  data["brand"] = stringPrettify(
    document.querySelector(selector.product_name)?.textContent || ' '
  ).split(" ")[1];
  data["description"] = stringPrettify(
    document.querySelector(selector.description)?.textContent || ' '
  );
  data["category"] = stringPrettify(
    document.querySelector(selector.category)?.textContent || ' '
  );
  return Array.from(document.querySelectorAll(selector.row)).map((e) => {
    return {
      ...data,
      color: stringPrettify(
        e.querySelector(selector.color)?.textContent || ' '
      ),
      price: stringPrettify(
        e.querySelector(selector.price)?.textContent || ' '
      ),
      warehouse1: stringPrettify(
        e.querySelector(selector.warehouse1)?.textContent || "0"
      ),
      warehouse2: stringPrettify(
        e.querySelector(selector.warehouse2)?.textContent || "0"
      ),
      size: stringPrettify(
        e.querySelector(selector.size)?.textContent || ' '
      ),
      img: e.querySelector(selector.img)?.src?.replace("-100x100", ""),
    };
  });
}

async function saveImages(prods) {
  const prodsImg = prods.map((e) => e.img);
  const res = await images(prodsImg, "./data/images");
  res.forEach((ob, index) => {
    prods[index]["local_image"] = ob.filename || "failed or no image";
  });
  return prods;
}

async function wait(number) {
  return new Promise((res) => setTimeout(res, number));
}

async function getProduct(product, page) {
  await page.goto(product, { timeout: 0, waitUntil: "domcontentloaded" });
  let productObjs = await page.evaluate(scrape);
  return await saveImages(productObjs);
  // return productObjs;
}

async function getNextPage(page) {
  const nextPage = await page.evaluate(
    () => document.querySelector(".next.page-number").href
  );
  await page.goto(nextPage, { timeout: 0, waitUntil: "domcontentloaded" });
  return await page.evaluate(() =>
    Array.from(document.querySelectorAll(".product-small.col")).map(
      (e) => e.querySelector("a")?.href
    )
  );
}

async function getBrandProducts(brand, page) {
  await page.goto(brand, { timeout: 0, waitUntil: "domcontentloaded" });
  let data = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".product-small.col")).map(
      (e) => e.querySelector("a")?.href
    )
  );
  let hasNextPage = await page.evaluate(
    () => !!document.querySelector(".next.page-number")
  );
  while (hasNextPage) {
    const s_data = await getNextPage(page);
    data = [...data, ...s_data];
    hasNextPage = await page.evaluate(
      () => !!document.querySelector(".next.page-number")
    );
  }
  return data;
}

async function getData(xlsxName) {
  if (config.useSession) {
    browser = await puppeteer.launch({ userDataDir: "./session_data" });
  } else {
    browser = await puppeteer.launch();
    //browser = await puppeteer.launch({headless: false});
  }
  const page = await browser.newPage();
  await page.goto("https://katisportcap.com/my-account/", {
    timeout: 0,
    waitUntil: "domcontentloaded",
  });
  let isLoggedIn = await page.evaluate(
    () => !!document.querySelector(".woocommerce-MyAccount-content")
  );
  console.log("Logged in: ", isLoggedIn);
  if (!isLoggedIn) {
    console.log("Logging in as", config.auth.user);
    await page.type("#username", config.auth.user);
    await page.type("#password", config.auth.pass);
    if (config.remember) {
      await page.click("#rememberme");
    }
    await page.click("button[type='submit'][name='login']");
    await page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 0 });
    isLoggedIn = await page.evaluate(
      () => !!document.querySelector(".woocommerce-MyAccount-content")
    );
    console.log("Logged in: ", isLoggedIn);
    if (!isLoggedIn) {
      console.error("Wrong Auth");
      return;
    }
  }
  console.log("Scanning Products");
  let cnfgproducts = [...config.products];
  let brands = [...config.brands];

  let brandNum = 1;
  for (let brand of brands) {
    const products = await getBrandProducts(brand, page);
    console.log(`total products found in brand ${brandNum}: `, products.length);

    if (cnfgproducts.length) {
      products = [...cnfgproducts, ...products];
      cnfgproducts = [];
    }

    let allScrapedProduct = [];

    console.log("getting products");
    for (let p of products) {
      const scrapedProduct = await getProduct(p, page);
      allScrapedProduct.push(scrapedProduct);
    }
    allScrapedProduct = allScrapedProduct.flat();
    console.log(`writing brand ${brandNum++} products...`);
    saveToSheet_full(allScrapedProduct, xlsxName);
    saveToSheet_min(allScrapedProduct, xlsxName);
  }
  browser.close();
}

async function main() {
  const xlsxName = `./data/xlsx/<folder>/${new Date().toISOString().replaceAll(":", "-")}.xlsx`;
  await getData(xlsxName);
  console.log("done");
}
main();
