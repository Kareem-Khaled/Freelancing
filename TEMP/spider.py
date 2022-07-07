from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import Chrome, ChromeOptions
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import captcha_solver
import time
import csv
import re

PATH = ChromeDriverManager().install()
capa = DesiredCapabilities.CHROME
driver = Chrome(PATH, desired_capabilities=capa)
wait = WebDriverWait(driver, 15)

results = []

file = open('Domains.txt', 'r')
websites = file.readlines()

def solve_recaptcha_if_existing(domain, driver):
    if "sorry" in driver.current_url and driver.current_url.find('?') != -1:
        print(f'Captcha in {driver.current_url}')
        print(f'Try to solve with 2Captcha.com')

        recaptcha = driver.find_element_by_id('recaptcha')
        googlekey = recaptcha.get_attribute('data-sitekey')
        data_s = recaptcha.get_attribute('data-s')
        pageurl = driver.current_url

        while True:
            res = captcha_solver.solve('c8fa0e739b6f68d9b40f9465b2ce5404', googlekey, pageurl, data_s, domain)

            if res == 'ERROR_CAPTCHA_UNSOLVABLE' or res == 'ERROR':
                print("Captcha unsolved")
                driver.get(driver.current_url)
                time.sleep(1/1000)
            elif res == 'ERROR_ZERO_BALANCE':
                print('\n\n')
                print("!!!   ERROR   !!!")
                print('You don\'t have enough balance to solve the captcha!')
                choose = int(input('Top up your balance and enter 1 or everything else for close script: '))
                if choose == 1:
                    driver.get(driver.current_url)
                    time.sleep(5)
                    continue
                else:
                    driver.close()
                    exit()
            else:
                print(f"Captcha solved for domain {domain}")
                g_recaptcha_response = driver.find_element_by_id('g-recaptcha-response')
                driver.execute_script("arguments[0].style.display = 'block';", g_recaptcha_response)
                time.sleep(2)

                driver.execute_script(f'arguments[0].innerHTML="{res}";', g_recaptcha_response)
                time.sleep(3)

                driver.find_element_by_id('captcha-form').submit()
                time.sleep(4)
                return
    elif "sorry" in driver.current_url and driver.current_url.find('?') == -1:
        driver.get('https://www.google.com')
        text_field = driver.find_element_by_xpath('//*[@id="tsf"]/div[2]/div[1]/div[1]/div/div[2]/input')
        text_field.send_keys(domain)
        text_field.send_keys(Keys.ENTER)
        return
    else:
        return

for website in websites:
    name = website.replace('\n', '').replace('.com', '')
    try:
        solve_recaptcha_if_existing(name, driver)
        time.sleep(3)
        print('Scraping: ', name)
        driver.get('https://www.google.com/search?hl=en&q=' + name)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.tjvcx')))

        try:
            element = driver.find_element_by_css_selector('.BYM4Nd')
            auth = 'Yes'
        except NoSuchElementException:
            auth = 'No'

        try:
            element = driver.find_element_by_css_selector('#lu_map')
            gmaps = 'Yes'
        except NoSuchElementException:
            gmaps = 'No'

        try:
            # time.sleep(22)
            soup = BeautifulSoup(driver.page_source, 'lxml')
            element = soup.find_all('div', class_ = 'fG8Fp uo4vr')
            print(str(element))
            reviews = element.span.text.split(' ')[0].replace(',', '')
        except NoSuchElementException:
            reviews = 'None'

        try:
            website_found = ''
            elements = driver.find_elements_by_css_selector('.tjvcx')
            for element in elements:
                try:
                    domain = element.text.split('/')[2].split(' ')[0].replace('www.', '')
                    if name in domain:
                        website_found += domain + ', '
                except:
                    continue
            if len(website_found) == 0:
                website_found = 'None'
            else:
                website_found = website_found[:-2]
        except NoSuchElementException:
            website_found = 'None'

        except NoSuchElementException:
            fb = 'None'

        result = {'Name': name, 'Website Found': website_found, 'Auth': auth, 'GMaps': gmaps, 'Reviews': reviews}
        results.append(result)
    except Exception as e:
        print(f"Error {e} for domain {name}")

dict_data = results
csv_columns = ['Name', 'Website Found', 'Auth', 'GMaps', 'Reviews']
csv_file = "websites.csv"
try:
    with open(csv_file, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
        writer.writeheader()
        for data in dict_data:
            writer.writerow(data)
except IOError:
    print("I/O error")

driver.close()