import os
import re
import warnings
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def save_image(driver, url, folder):

    # To soave the original image
    driver.get(url)
    data = driver.execute_script("return fetch(arguments[0]).then(response => response.arrayBuffer()).then(buffer => new Uint8Array(buffer));", url)

    # Make sure that it's a valid folder name
    folder = re.sub(r'[^\w.]+', '_', folder)
    folder = re.sub(r'__+', '_', folder)

    # Determine which folder to save the image
    folder_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'Scraped images', folder)
    
    image_name = os.path.basename(url)
    image_path = os.path.join(folder_path, image_name)

    # Create the folder if it does not exist
    os.makedirs(folder_path, exist_ok=True)

    # Saving the image
    with open (image_path, 'wb') as f:
        f.write(bytes(data))

# Ignore unnecessary warnings
warnings.filterwarnings("ignore", category = DeprecationWarning)

def get_images(links, password):

    # Chrome options
    options = ChromeOptions()
    options.add_argument('--headless')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    with webdriver.Chrome(ChromeDriverManager().install(), options = options) as driver:
        for url in links:

            # If it needs password, use it
            try: 
                driver.get(url)
                driver.find_element(By.ID, 'indexlock__input').send_keys(password)
                driver.find_element(By.ID, 'indexlock__ok').click()
            except: pass

            # Waiting images to load
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "image__clickhandle")))

            try:
                # Getting the product name
                soup = BeautifulSoup(driver.page_source, 'lxml')
                name = soup.find('h2').span['data-name'].encode('utf-8').decode('utf-8') or 'Undefined'
            except:
                pass

            # Getting the id of all images
            ids = soup.find_all('div', {'class' : 'image__clickhandle'})
            print(f'\n->> Geting {name} images...', flush = True)
            print('->>', end = ' ', flush = True)

            # Iterate over ids and save images
            idx = 0
            for id in ids:
                idx += 1
                print(f'{idx}', end = ', ', flush = True)
                try:
                    url = f'https://friends0818.x.yupoo.com/{id["data-photoid"]}?uid=1'
                    driver.get(url)
                    soup = BeautifulSoup(driver.page_source, 'lxml')
                    img = soup.find('div', {'class' : 'viewer__imgwrap'}).find('img')['src']
                    save_image(driver, 'https:' + img, name)
                except:
                    pass

        print('Done!', flush=True)

if __name__ == '__main__':
    with open('password.txt', 'r') as file:
        password = file.readline()

    with open('links.txt', 'r') as file:
        links = file.readlines()

    links = [s.strip() for s in links if s.strip()]
    get_images(links, password)