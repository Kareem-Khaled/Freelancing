import os
import smtplib
import time
import warnings
from email.message import EmailMessage
from bs4 import BeautifulSoup
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
options = ChromeOptions()
options.headless = True
warnings.filterwarnings("ignore", category=DeprecationWarning)
options.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = Chrome(executable_path = os.getcwd() + '\chromedriver', options=options)
website = "https://publico.elterrat.com/programa/la-resistencia/formulario/"
cookies = {
        "name": "PHPSESSID",
        "value": "hr4qm66bpt030gg3gav7fb89h2"
}

def check():
        wr = 0
        while wr < 3:
         try:
                driver.refresh()
                calendar = driver.find_element_by_id('field_1_28-2-1')
                actions = ActionChains(driver)
                actions.move_to_element(calendar).click().perform()
                time.sleep(2)

                soup = BeautifulSoup(driver.page_source, 'lxml')
                table = soup.find('table',{'class':'ui-datepicker-calendar'})
                trs = table.tbody.find_all('tr')
                for tr in trs:
                        for td in tr:
                                if 'lleno' not in td['class'] and 'undefined' not in td['class']:
                                       return 1
                return 0
         except Exception as e:
                print("--------- Technical - Error ---------")
                print(e)
                print("--------- Technical - Error ---------")
                wr += 1
                if wr == 3:
                        return 2
def sendEmail(m):
        try:
                msg = EmailMessage()
                msg.set_content(m)
                msg['Subject'] = 'Bot Alert'
                msg['From'] = "...@gmail.com"
                msg['To'] = "...@gmail.com"
                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login("...@gmail.com", "PASSWORD")
                server.send_message(msg)
                server.quit()
                print('- Mail sent!', flush=True)
        except Exception as e:
                print("--------- Technical - Error ---------")
                print(e)
                print("--------- Technical - Error ---------")
                print("- Error while sending the mail", flush=True)

def changeCookies():
        try:
                driver.delete_all_cookies()
                cookies['value'] = input('- Enter the cookie value: ')
                driver.add_cookie(cookies)
        except Exception as e:
                print("--------- Technical - Error ---------")
                print(e)
                print("--------- Technical - Error ---------")
                print("- Error while adding cookies", flush=True)


if __name__ == '__main__':
              try:
                   print('- Starting...')
                   driver.get(website)
                   changeCookies()
                  
                   while 1:
                        print("- Checking...", flush=True)
                        ret = check()
                        if ret == 1:
                                print("- Sending Email...", flush=True)
                                sendEmail("There is a green cells!!!")
                        elif ret == 2:
                                print("- Cookies Error...", flush=True)
                                sendEmail("Please check your cookies :(")
                                changeCookies()
                                continue
                        else:
                                print("- There is no green cells :(", flush=True)
                        print("- We will check again after 5 minutes...", flush=True)
                        for x in range(5):
                            time.sleep(60)
                            print(x + 1, end='. ', flush=True)
                        print('')
              except Exception as e:
                        print("--------- Technical - Error ---------")
                        print(e)
                        print("--------- Technical - Error ---------")
                        print("- Unpredicted error happened please restart the bot", flush=True)