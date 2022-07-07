import os
import sys
import time
import warnings
import subprocess
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import Chrome, ChromeOptions

try:
    from selenium import __version__ as selenium_version
    print(f"Selenium Version:\n{selenium_version}\n")
    if "3.14" not in selenium_version:
        print('* Incompatible Selenium version detected. Reinstalling Selenium...')
        subprocess.check_call([sys.executable, "-m", "pip", "install", 'selenium==3.14.0'])
        print('\n-----------------------------------------------------------------------------\n')
except ImportError:
    print('* Selenium not found. Installing Selenium...')
    subprocess.check_call([sys.executable, "-m", "pip", "install", 'selenium==3.14.0'])
    print('\n-----------------------------------------------------------------------------\n')

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
options = ChromeOptions()
options.headless = True
warnings.filterwarnings("ignore", category = DeprecationWarning)
options.add_experimental_option('excludeSwitches', ['enable-logging'])
options.add_argument("--disable-notifications")
driver = Chrome(executable_path = os.getcwd() + '\chromedriver', options=options)
try:
    __import__('BeautifulSoup')
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", 'beautifulsoup4'])

try:
    __import__('pwinput')
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", 'pwinput'])

from bs4 import BeautifulSoup
import pwinput

file = open('out.txt', 'w', encoding="utf-8")

def getNewUsers(mail, psw, url, tt):
    try:
        driver.get('https://www.facebook.com/')
        _ = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "email")))
        driver.find_element_by_id('email').send_keys(mail)
        pas = driver.find_element_by_id('pass')
        pas.send_keys(psw)
        pas.send_keys(Keys.ENTER)
        time.sleep(5)
        code = input("->> please enter the verification code: ")
        if len(code):
            try: 
                _ = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "approvals_code")))
                aprv = driver.find_element_by_id('approvals_code')
                aprv.send_keys(code)
                aprv.send_keys(Keys.ENTER)
            except: pass
        time.sleep(10)
        driver.get(url + '/members')
        time.sleep(5)
        print("->> Searching...", flush = True)
        file.write(f"Members joined in the last {tt} hours:\n")
        file.write("======================\n")
        cur = 1
        while cur < 12:
            try:
                cur += 1
                # webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                time.sleep(5)
                soup = BeautifulSoup(driver.page_source, 'lxml')
                all = soup.find_all('div', class_ = 'b20td4e0 muag1w35')
                try:
                    news = all[-2].find_all('div', role = "listitem")
                    date = news[-1].find('span', class_ = 'd2edcug0 hpfvmrgz qv66sw1b c1et5uql lr9zc1uh sq6gx45u j5wam9gi lrazzd5p m9osqain').text
                except:
                    news = all[-1].find_all('div', role = "listitem")
                    date = news[-1].find('span', class_ = 'd2edcug0 hpfvmrgz qv66sw1b c1et5uql lr9zc1uh e9vueds3 j5wam9gi lrazzd5p m9osqain').text
                joinedon = date.find('Joined on')
                joinedlast = date.find('Joined last')
                if joinedon != -1 or joinedlast != -1: break
            except Exception as e:
                print("- There is some erorr in (searching), please restart the bot")
                print(str(e))
        print("->> Collecting...", flush = True)
        id = 1
        for user in news:
            try:
                link = user.find('a')['href']
                link = 'https://www.facebook.com/profile.php?id=' + str(link).split('/')[-2]
            except: continue
            try:
                date = user.find('span', class_ = 'd2edcug0 hpfvmrgz qv66sw1b c1et5uql lr9zc1uh sq6gx45u j5wam9gi lrazzd5p m9osqain').text
            except:
                date = user.find('span', class_ = 'd2edcug0 hpfvmrgz qv66sw1b c1et5uql lr9zc1uh e9vueds3 j5wam9gi lrazzd5p m9osqain').text
            joinedon = date.find('Joined on')
            joinedlast = date.find('Joined last')
            if joinedon != -1 or joinedlast != -1: break
            hr = date.find('hour')
            hrs = date.find('hours')
            if hr != -1 or hrs != -1:
                t = [int(s) for s in date.split() if s.isdigit()]
                if len(t) and t[0] > tt: break
                file.write(f"{id}- {link}\n")
                id += 1
                file.write("======================\n")
            else:
                file.write(f"{id}- {link}\n")
                id += 1
                file.write("======================\n")
   
    except Exception as e:
            print("- There is some erorr in (collecting), please restart the bot")
            print(str(e))

if __name__ == "__main__":
    print("====================================================================", flush = True)
    print("->> Starting...", flush = True)
    mail = input("->> please enter your facebook email: ")
    psw =  pwinput.pwinput("->> please enter your facebook password: ")
    url = input("->> please enter the group url: ")
    tt = int(input("->> please enter the maximum time you want: "))
    getNewUsers(mail, psw, url, tt)
    print("->> Done!!!", flush = True)
    driver.quit()
    file.close()
