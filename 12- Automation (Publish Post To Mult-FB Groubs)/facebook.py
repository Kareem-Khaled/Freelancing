import pip
import time
import warnings
import importlib.util
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains

if importlib.util.find_spec('openpyxl') is None:
    pip.main(['install', 'openpyxl']) 

if importlib.util.find_spec('pandas') is None:
    pip.main(['install', 'pandas']) 

if importlib.util.find_spec('pwinput') is None:
    pip.main(['install', 'pwinput']) 

if importlib.util.find_spec('pyperclip') is None:
    pip.main(['install', 'pyperclip']) 

options = ChromeOptions()
warnings.filterwarnings("ignore", category = DeprecationWarning) 
options.add_experimental_option('excludeSwitches', ['enable-logging']) # remove warnings
options.add_argument("--disable-notifications") # hide pop-ups
driver = webdriver.Chrome(ChromeDriverManager().install(), options = options)
driver.maximize_window()

import pwinput
import pyperclip
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def run(mail, psw, sheet_name, delay):
    try:
        driver.get('https://www.facebook.com/')
        _ = WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.ID, "email")))
        driver.find_element_by_id('email').send_keys(mail)
        pas = driver.find_element_by_id('pass')
        pas.send_keys(psw)
        pas.send_keys(Keys.ENTER)
        code = input("->> please enter the verification code (if you don't have, just press enter): ")
        if len(code):
            try: 
                _ = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "approvals_code")))
                aprv = driver.find_element_by_id('approvals_code')
                aprv.send_keys(code)
                aprv.send_keys(Keys.ENTER)
            except: pass
    except: print(f"- error in login") 

    try:
        df = pd.read_excel('groups.xlsx',engine='openpyxl', sheet_name=sheet_name,dtype=object,header=None)
        groups = df.values.tolist()
    except: print("- error in groups.xlsx file")

    try:
        f = open('post.txt', 'r', encoding="utf-8")
        txt = f.read()
        pyperclip.copy(txt)
        f.close()
    except: print("- error in post post file")

    wr = 0
    i = 0
    while i < len(groups):
        try:
            if wr >= 3: 
                i += 1
                wr = 0
                continue
            print(f'- in group [{i + 1}] - {groups[i][0]}')
            driver.get(groups[i][0])
            actions = ActionChains(driver)
            addPost = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[4]/div/div/div/div/div/div[1]/div[1]/div/div/div/div[1]/div")))   
            actions.move_to_element(addPost).click().perform()  
            post = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[1]/div/div[4]/div/div/div[1]/div/div[2]/div/div/div/div/div[1]/form/div/div[1]/div/div/div[1]/div/div[3]/div[2]/div/div")))
            actions = ActionChains(driver)
            actions.key_down(Keys.LEFT_CONTROL)
            actions.move_to_element(addPost).send_keys('v')
            actions.key_up(Keys.LEFT_CONTROL)
            actions.move_to_element(post).click().perform()
            time.sleep(delay)
            wr = 0
            i += 1
        except Exception as e:
            print(f"- error in group {i + 1} trying again...") 
            wr += 1
    
if __name__ == '__main__':
    print("====================================================================", flush = True)
    print("->> Starting...", flush = True)
    mail = input("->> please enter your facebook email: ")
    psw = pwinput.pwinput("->> please enter your facebook password: ")
    sheet_name = input('->> please enter the name of the sheet you want: ')
    delay = int(input('->> please enter the delay between each post: '))
    run(mail, psw, sheet_name, delay)
    print("->> Done!!!", flush = True)
    driver.quit()