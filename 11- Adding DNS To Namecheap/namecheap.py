import pip
import time
import warnings
import importlib.util
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
options = ChromeOptions()

#Path to chrome profile to open with my credentials
# options.add_argument("user-data-dir=C:\\Users\\kemo\\AppData\\Local\\Google\\Chrome\\User Data") 

warnings.filterwarnings("ignore", category = DeprecationWarning)
options.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = webdriver.Chrome(ChromeDriverManager().install(), options = options)
driver.maximize_window()

if importlib.util.find_spec('pyperclip') is None:
    pip.main(['install', 'pyperclip']) 

import pyperclip

try:
    driver.get('https://www.namecheap.com/myaccount/login-signup/')
    _ = WebDriverWait(driver, 50).until(
        EC.presence_of_element_located((By.CLASS_NAME, "nc_username")))
    username = input('->> Please enter the username: ')
    password = input('->> Please enter the password: ')
    driver.find_element_by_class_name('nc_username').send_keys(username)
    driver.find_element_by_class_name('nc_password').send_keys(password)
    _ = WebDriverWait(driver, 50).until(
        EC.presence_of_element_located((By.CLASS_NAME, "nc_login_submit")))
    actions = ActionChains(driver)
    actions.move_to_element(driver.find_element_by_class_name('nc_login_submit')).click().perform()
except Exception as e: 
    print("->> Erorr in login")

try:
    code = input("->> Please enter the verification code (if you don't have, just press enter): ")
    driver.find_element_by_id('codeInput').send_keys(code)
    actions = ActionChains(driver)
    actions.send_keys(Keys.ENTER).perform()
except: pass

try:
    domain = input('->> Please enter the domain name: ')
    url = f'https://ap.www.namecheap.com/Domains/DomainControlPanel/{domain}/advancedns'
    time.sleep(5)
    driver.get(url)
except: print("->> Erorr in domain name")

record = {
    'A':0,
    'A+':1,
    'AAAA':2,
    'ALIAS':3,
    'CAA':4,
    'CNAME':5,
    'NS':6,
    'SRV':7,
    'TXT':8,
    'URL':9
}

ttl = {
    '':1,
    '60':2,
    '30':3,
    '20':4,
    '5':5,
    '1':6
}

row_num = -1
try:
    for line in open("DNS Sequence.csv"):
        while True:
            try:
                actions = ActionChains(driver)
                actions.move_to_element(driver.find_element_by_xpath('/html/body/div[1]/div[3]/div/div/div[2]/div[5]/div/div[3]/div[1]/div[2]/div[2]/div[2]/div/table/tbody[3]/tr/td/div[1]/a[1]')).click().perform()
                break
            except Exception as e: pass
        try:
            row_num += 1
            row = line.strip().split(',')
            print(f"->> In row {row_num} - {row}")

            #0
            actions = ActionChains(driver)
            actions.send_keys(Keys.UP * 10)
            actions.send_keys(Keys.DOWN * record[row[0]])
            actions.send_keys(Keys.TAB).perform()

            #1, 2
            i = 1
            while i < 3:
                actions = ActionChains(driver)
                pyperclip.copy(row[i])
                actions.key_down(Keys.LEFT_CONTROL)
                actions.send_keys('v')
                actions.key_up(Keys.LEFT_CONTROL)
                actions.send_keys(Keys.TAB).perform()
                i += 1

            #3
            try:
                actions = ActionChains(driver)
                if row[0] == 'ALIAS':
                    if row[3] == 1: actions.send_keys(Keys.DOWN * 3)
                    elif row[3] == 5: actions.send_keys(Keys.DOWN * 2)
                    else: actions.send_keys(Keys.DOWN)
                elif row[0] == 'URL': 
                    actions.send_keys(Keys.DOWN)
                else:
                    actions.send_keys(Keys.DOWN * ttl[row[3]])
            except: pass
            actions.send_keys(Keys.TAB).perform()
            
            #4
            actions = ActionChains(driver)
            actions.send_keys(Keys.ENTER).perform()
            time.sleep(2)
        except: pass
except: 
    print(f"->> Error in row {row_num} - DNS Sequence")
driver.quit()