import os
import time
import random
import requests
import warnings
import threading
import urllib.request
import concurrent.futures
from helper import Methods
from bs4 import BeautifulSoup
from selenium import webdriver
from requests_html import HTMLSession
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from concurrent.futures import ThreadPoolExecutor
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

website_name = 'url'
# Ignore unnecessary warnings
warnings.filterwarnings("ignore", category = DeprecationWarning)

def get_urls():
    urls = []
    max_wr, slp = methods.max_wr, methods.slp

    wr = 0
    while wr < max_wr:
        try:
            session = HTMLSession()
            src = session.get('url')
            soup = BeautifulSoup(src.html.raw_html, 'lxml')
            break
        except:
            wr += 1
            time.sleep(slp * wr)

    if wr == max_wr:
        return

    return urls

def save_image(url, is_logo = None):
    # Create the images folder if it doesn't exist
    dir_prfx = f'{website_name}_Images'
    if not os.path.exists(dir_prfx):
        os.makedirs(dir_prfx)

    image_name = dir_prfx + '/' + os.path.basename(url)

    if is_logo:
        try:
            urllib.request.urlretrieve(url, image_name)
        except:
            try:
                response = requests.get(url)
                with open(image_name, 'wb') as f:
                    f.write(response.content)
            except:
                return ''
    else:
        try:
            response = requests.get(url)
            with open(image_name, 'wb') as f:
                f.write(response.content)
        except:
            return ''

    return image_name

def get_data(link):
    max_wr, slp = methods.max_wr, methods.slp
    last_data, urls, url_lock = methods.last_data, methods.urls, methods.url_lock

    # Chrome options
    options = ChromeOptions()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.104 Safari/537.36"
    options.add_argument('--headless')
    options.add_argument(f'user-agent={user_agent}')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    with webdriver.Chrome(ChromeDriverManager().install(), options = options) as driver:

        driver.set_window_size(1920, 1080)
        driver.get(link)
        while True:
            wr = 0
            data = None
            while wr < max_wr:
                try:
                    WebDriverWait(driver, 6).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "listing-holder")))
                    soup = BeautifulSoup(driver.page_source, 'lxml')
                    data = soup.find_all()

                    with url_lock:
                        pass

                    if data: break
                    wr += 1
                    time.sleep(slp* wr)

                except:
                    wr += 1
                    time.sleep(slp* wr)

def download_data(id):
    max_wr, slp = methods.max_wr, methods.slp
    urls, url_lock = methods.urls, methods.url_lock
    session = HTMLSession()
    while True:
        url = None
        empty_time = time.time()
        while True:
            with url_lock:
                if urls:
                    empty_time = time.time()
                    url = urls.pop()
                    break

            if not url:
                if time.time() - empty_time > 60: # finished
                    # print(f'[{id}-die]', flush=True, end='.')
                    return
                else: # try again (idle mode)
                    # print(f'[{id}-idle]', flush=True, end='.')
                    time.sleep(slp / 2)

        # print(f'[{id}-in]', flush=True, end='.')

        wr = 0
        while wr < max_wr:
            try:
                src = session.get(url)
                soup = BeautifulSoup(src.html.raw_html, 'lxml')
                break
            except:
                wr += 1
                time.sleep(slp * wr)

        if wr == max_wr:
            continue

        try:
            imgs, tmp = [], []
            with ThreadPoolExecutor(max_workers = 10) as executor:
                for img in tmp:
                    try:
                        future = executor.submit(save_image, img)
                        imgs.append(future.result())
                    except: pass
        except: imgs = ''

        data = []
        methods.write(f'{id} - {len(urls)}', data)

if __name__ == '__main__':
    print('\033[32;1;14mDeveloped by Kareem_Khaled --- Email: kareemkhaled143@gmail.com\n---------------------------------------------------------------\033[0m', flush=True)

    start_time = time.time()
    print('->> Check existing data...\n', flush=True)
    methods = Methods(f'{website_name}.xlsx')

    print('->> Getting search URLs...\n', flush=True)
    links = get_urls()

    thrd = (int(input('->> Please enter the number of threads: ')) + 1) // 2

    print('\n->> Collecting the data...\n', flush=True)

    # Start add_data threads
    threads = []
    for id in range(thrd):
        add_thread = threading.Thread(target=download_data, args=(id,))
        add_thread.start()
        threads.append(add_thread)

    # Execute get_data asynchronously using a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=thrd) as executor:
        futures = [executor.submit(get_data, link) for link in links]

    # Wait for all get_data futures to complete
    for future in futures:
        future.result()

    # Wait for all add_data threads to finish
    for thread in threads:
        thread.join()

    methods.last_save()

    end_time = time.time()

    elapsed_time = end_time - start_time
    elapsed_time_in_minutes = elapsed_time / 60

    print(f"\n\nProgram completed in {elapsed_time_in_minutes:.2f} minutes.")
