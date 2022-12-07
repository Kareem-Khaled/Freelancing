import os
import smtplib
import time
import warnings
from email.message import EmailMessage
from bs4 import BeautifulSoup
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
options = ChromeOptions()
#options.headless = True
warnings.filterwarnings("ignore", category=DeprecationWarning)
options.add_experimental_option('excludeSwitches', ['enable-logging'])
options.add_extension('Buster--Captcha-Solver-for-Humans.crx')
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
         except:
                wr += 1
                if wr == 1:
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
                print('- Mail sent!')
        except:
                print("- Error while sending the mail")

def captchaSolver():
        try:
                driver.delete_all_cookies()
                driver.refresh()
                time.sleep(2)
                captcha = driver.find_element_by_class_name('g-recaptcha')
                submit = driver.find_element_by_class_name('gform_button')
                actions = ActionChains(driver)
                actions.move_to_element(captcha).click().perform()
                time.sleep(2)
                iframe = driver.find_elements_by_xpath('/html/body/div/div[4]/iframe')[0]
                driver.switch_to.frame(iframe)
                solve = driver.find_element_by_class_name('help-button-holder')
                actions.move_to_element(solve).click().perform()
                time.sleep(5)
                actions.move_to_element(submit).click().perform()
                time.sleep(2)
                cookies['value'] = driver.get_cookies()[0]['value']
                driver.add_cookie(cookies)
        except:
                print("- Error while solving the captcha")

if __name__ == '__main__':
              try:
                   print("- Starting...")
                   driver.get(website)
                   driver.delete_all_cookies()
                   driver.add_cookie(cookies)
                   errr = 0
                   while 1:
                        print("- Checking...")
                        ret = check()
                        if ret == 1:
                                print("- Sending Email...")
                                sendEmail("There is a green cells!!!")
                                errr = 0
                        elif ret == 2:
                                print("- Cookies Error...")
                                print("- Trying to solve the captcha...")
                                captchaSolver()
                                errr += 1
                                if errr == 3:
                                        sendEmail("Please give me a valid cookies")
                                        print("- I can't solve this captch :(")
                                        cookies['value'] = input('- Please enter the cookie value: ')

                        else:
                                print("- There is no green cells :(")
                                errr = 0
                        print("- We will check again after 5 minutes...")
                        time.sleep(3)
              except:
                        print("- Unpredicted error happened please restart the bot")