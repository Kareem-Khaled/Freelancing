import os
import warnings
import threading
import xlsxwriter
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
options = ChromeOptions()
options.headless = True
warnings.filterwarnings("ignore", category = DeprecationWarning)
options.add_experimental_option('excludeSwitches', ['enable-logging'])
urls = []
file = open('out.txt', 'w')
def get_all(url, id):
    try :
        global cur
        print(f"[{id}] + {url}\n")
        driver = Chrome(executable_path = os.getcwd() + '\chromedriver', options=options)
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, 'lxml')
        books = soup.find('ul', class_ = 'products')
        booksLinks = books.find_all('a', class_ = 'product')
        for link in booksLinks:
            try:
                driver.get(link['href'])
                soup = BeautifulSoup(driver.page_source, 'lxml')
                name = WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "base")))
                img = soup.find('img', class_ = 'fotorama__img')
                authors = soup.find_all('div', class_ = 'product-brand-name')
                price = soup.find('span', class_ = 'price')
                description = soup.find('div', id = 'description')
                isbn = soup.find('td', {'data-th' : 'ISBN'})
                pages = soup.find('td', {'data-th' : 'Number of pages'})
                auth = ''
                for author in authors:
                    auth += str(author.span.text) + ', '
                auth = auth[:-2]
                data = [name.text, auth, price.text, id, str(pages.text), str(isbn.text) ,description.text, img['src'], link['href']]
                print(id, flush=True, end='.')
                if cur == 0:
                    writing(data)
                elif cur == 1:
                    writing1(data)
                else:
                    writing2(data)
                cur += 1
                cur %= 3
            except Exception as e:
                file.write(f"{link}\n")
                print("- Error in booksLinks")
                print(str(e))
        print(f"\n[{id}] - {url}\n")
    except Exception as e:
        print(f"- Error in get_all - {url}")
        print(str(e))

row = 0
row1 = 0
row2 = 0
cur = 0

writer_lock = threading.Lock()
writer1_lock = threading.Lock()
writer2_lock = threading.Lock()

workbook = xlsxwriter.Workbook('1- #.com.xlsx')
worksheet = workbook.add_worksheet("data")
bold = workbook.add_format({'bold': True})

workbook1 = xlsxwriter.Workbook('1- #.com1.xlsx')
worksheet1 = workbook1.add_worksheet("data")

workbook2 = xlsxwriter.Workbook('1- #.com2.xlsx')
worksheet2 = workbook2.add_worksheet("data")

def writing(data):
    try:
        print('[0]', flush=True, end='.')
        with writer_lock:
            global row
            col = 0
            for key in (data):
                worksheet.write(row, col, key)
                col += 1
            row += 1
    except Exception as e:
        print("- Error in writing")
        print(str(e))

def writing1(data):
    try:
        print('[1]', flush=True, end='.')
        with writer1_lock:
            global row1
            col = 0
            for key in (data):
                worksheet1.write(row1, col, key)
                col += 1
            row1 += 1
    except Exception as e:
        print("- Error in writing1")
        print(str(e))

def writing2(data):
    try:
        print('[2]', flush=True, end='.')
        with writer2_lock:
            global row2
            col = 0
            for key in (data):
                worksheet2.write(row2, col, key)
                col += 1
            row2 += 1
    except Exception as e:
        print("- Error in writing2")
        print(str(e))

if __name__ == '__main__':
    try:
        data = ['Book_name', 'Author', 'Price', 'Category', 'Pages_num', 'ISBN','Description','Image_link', 'Book_link']
        col = 0
        for key in (data):
            worksheet.write(row, col, key, bold)
            col += 1
        row += 1
        with ThreadPoolExecutor(max_workers = 3) as executor:
            id = 0
            for url in urls:
                executor.submit(get_all, url, id)
                id += 1
        workbook.close()
        workbook1.close()
        workbook2.close()
        file.close()
        print("FINISH :)")
    except Exception as e:
        print("- Error in main")
        print(str(e))