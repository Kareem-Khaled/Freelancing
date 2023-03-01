import time
import warnings
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC

options = ChromeOptions()
warnings.filterwarnings("ignore", category = DeprecationWarning) 
options.add_experimental_option('excludeSwitches', ['enable-logging']) # remove warnings
options.headless = True
driver = webdriver.Chrome(ChromeDriverManager().install(), options = options)
# driver.maximize_window()

email = '#'
password = '#'

def closeBtn():
    WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div/div/section/header/button"))).click()

if __name__ == '__main__':
    try:
        print('->> Logging in...', flush=True)
        # login
        driver.get('https://go.xero.com')
        _ = WebDriverWait(driver, 50).until(
                EC.presence_of_element_located((By.ID, "xl-form-email")))

        driver.find_element(By.ID, 'xl-form-email').send_keys(email)
        driver.find_element(By.ID, 'xl-form-password').send_keys(password)
        driver.find_element(By.ID, 'xl-form-submit').click()

        input('->> Press Enter after approve the login...')
        time.sleep(5)
        print('->> Logged in!', flush=True)
        driver.get('https://go.xero.com/app/!H6-l4/contacts/all')
        try:
            closeBtn()
        except:
            pass

        total = WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.CLASS_NAME, "xui-pagination--items--count")))
        total = int(total.text.split()[-1])
        print(f'->> Checking {total} Contacts...', flush = True)

        allContacts = 0
        avaliableContacts = []
        while allContacts < total:

            contacts = []
            while not len(contacts):
                soup = BeautifulSoup(driver.page_source, 'lxml')
                contacts = soup.find('table').find('tbody')
                time.sleep(1)

            for contact in contacts:
                a = contact.find_all('a')[-1]
                link = a['href']
                invoice = a.text
                allContacts += 1
                if not len(invoice):
                    avaliableContacts.append(link)

            # next-page
            nav = driver.find_elements(By.TAG_NAME, 'nav')[-1]
            nav.find_elements(By.TAG_NAME, 'button')[-1].click()


        idx = 0
        print(f'->> {len(avaliableContacts)} Contacts avaliable for sending invoices...', flush = True)
        for contact in avaliableContacts:
            wr = 0
            idx += 1
            print(f'->> Sending to contact {idx}...', flush = True)
            try:
                while wr < 2:
                    url = contact.split('/')[-1]
                    driver.get(f'https://invoicing.xero.com/?contactId={url}')
                    table = WebDriverWait(driver, 50).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table")))

                    table.find_elements(By.TAG_NAME, 'td')[1].click()
                    time.sleep(2)
                    driver.find_elements(By.CLASS_NAME, 'xui-pickitem--body')[-1].click()
                    time.sleep(2)
                    driver.find_element(By.ID, 'ApproveAndEmailButton-approve-and-email').click()
                    
                    _ = WebDriverWait(driver, 50).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "xui-actions--primary")))

                    _ = WebDriverWait(driver, 50).until(
                        EC.presence_of_element_located((By.ID, "AttachPDF-label")))

                    time.sleep(2)
                    driver.find_element(By.ID, 'AttachPDF-label').click()

                    driver.find_elements(By.CLASS_NAME, 'xui-actions--primary')[-1].click()

                    break
            except:
                wr += 1
                time.sleep(2)

            time.sleep(3)

        print("->> Finished", flush = True)
        driver.quit()

    except Exception as e:
        print("->> There is an error, Please restart the bot...", flush = True)
        print(e)