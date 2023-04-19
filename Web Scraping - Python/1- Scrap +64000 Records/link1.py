import os
import time
from bs4 import BeautifulSoup
from selenium.webdriver import Chrome, ChromeOptions
import warnings
import xlsxwriter

warnings.filterwarnings("ignore", category=DeprecationWarning)
options = ChromeOptions()
options.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = Chrome(executable_path = os.getcwd() + '\chromedriver', options=options)

website = "https://gproc.oabgo.org.br/pgs/consultamembroconselho.aspx"
try:
    driver.get(website)
    src = driver.page_source
    soup = BeautifulSoup(src, 'lxml')
    captcha = input('- Please enter captcha text:-\n')
    captchaText = driver.find_element_by_id("m_CaptchaText")
    captchaText.send_keys(captcha)
    searchBtb = driver.find_element_by_id("A2")
    searchBtb.click()
    time.sleep(10)
except:
    print('=== there is a problem in the website please restart the app ===')

page = 1
wr = 0
file = open("pages.txt", 'w')
print("- Getting all the pages...")
while page < 4005:
    try:
        if page != 1 and page % 10 == 1:
            driver.find_elements_by_link_text('...')[-1].click()
            time.sleep(1)
        elif page != 1:
            driver.find_element_by_link_text(str(page)).click()

        src = driver.page_source
        soup = BeautifulSoup(src, 'lxml')
        TDS = soup.find('div',{'id':'m_dvGridPessoa'}).find('table').findAll('td')
        for TD in TDS:
            a = TD.find('a')
            if a == None or not a.has_attr('onclick'):
                continue   
            l = str(a['onclick']).find('&') + 1
            r = str(a['onclick']).find(')') + 1
            link = 'https://gproc.oabgo.org.br/pgs/InformacoesEnderecoWeb.aspx?'+str(a['onclick'])[l:r]
            if page > 1991 and page < 4003:
                file.write(f"{str(link)}\n")
        if page > 4002:
            break
            
        print(f"- page: {page} doneee.")
        page += 1
        wr = 0

    except:
        time.sleep(1)
        print("hmmmmmm.")
xlsxwriter
file.close()
print(f"Done :) {page}")