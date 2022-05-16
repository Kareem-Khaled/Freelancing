import os
import sys
import time
import random
import subprocess
import warnings
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
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
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions


def get_emails():
    with open(emails_file_path, 'r') as emails_file:
        emails_list = emails_file.read().replace('\n\n', '\n').split('\n')

    print(f'Emails count: {len(emails_list)}')
    return emails_list


def edit_emails(email_to_be_removed):
    emails.remove(email_to_be_removed)
    with open(emails_file_path, 'w') as emails_file:
        emails_file.write('\n'.join(emails))


def get_links():
    with open(links_file_path, 'r') as links_file:
        links_list = links_file.read().replace('\n\n', '\n').split('\n')

    print(f'Links count: {len(links_list)}')
    return links_list


def get_extensions():
    with open(extensions_file_path, 'r') as extensions_file:
        extensions_data = extensions_file.read().split('\n')
        for extension_data in extensions_data:
            extensions_dict[extension_data.split(':')[0].strip(' ')] = \
                        get_path(extension_data.split(':')[1].strip(' '), extension_data.split(':')[0].strip(' '))


def get_path(additional_path, addition_name):
    path_to_file = os.path.join(PARENT_PATH, additional_path)
    print(f'{addition_name} Path: {path_to_file}')

    return path_to_file


PARENT_PATH = os.path.dirname(os.path.abspath(__file__))

print('File Paths:')
emails_file_path = get_path(r'EMAILs.txt', 'Emails file')
links_file_path = get_path(r'LINKs.txt', 'Links file')
extensions_file_path = get_path(r'EXTENSIONS.txt', 'Extensions file')
print()

print('Extension Paths:')
extensions_dict = {}
get_extensions()
print()

print('File Data:')
emails = get_emails()
links = get_links()


print('\n-----------------------------------------------------------------------------\n')


options = ChromeOptions()
warnings.filterwarnings("ignore", category=DeprecationWarning)
options.add_experimental_option('excludeSwitches', ['enable-logging'])


for name, path in extensions_dict.items():
    options.add_extension(path)
driver = webdriver.Chrome(executable_path = os.getcwd() + '\chromedriver', options=options)

number_of_iterations = int(input('[!] Number of Loops:\n'))
print()
delay = input('[!] Delay between links (e.g 40-60):\n').split('-')
print()
email_usage = int(input('[!] Number of times an email is used:\n'))
print()
input('[!] Press enter when VPN is enabled...')

print('[+] Bot started.\n')

e = 0
email = ''
for _ in range(number_of_iterations):
    print(f'\n[ITERATION: {_ + 1}]\n')
    i = 1
    for link in links:
        try:
            while True:
                try:
                    wait = random.randint(int(delay[0]), int(delay[1]))
                except ValueError:
                    wait = random.randint(int(delay[1]), int(delay[0]))

                print(f'[{i}] Working with: {link}')
                driver.get(link)
                time.sleep(wait)

                q5 = WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.ID, "q5")))

                driver.execute_script("arguments[0].style.display = 'block';", q5)

                email_field = q5.find_element_by_tag_name('input')
                if e % email_usage == 0 or e == 0:
                    email = random.choice(emails)
                print(f'\t- Using email: {email}')
                email_field.send_keys(email)
                time.sleep(5)
                email_field.send_keys(" ")
                time.sleep(3)
                
                submit_button = driver.find_element_by_id('subbtn')
                driver.execute_script("arguments[0].click();", submit_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", submit_button)

                i += 1
                e += 1
                if e % email_usage == 0:
                    edit_emails(email)

                time.sleep(10)

                print(f'\t- Waiting {wait} seconds...\n')
                time.sleep(wait)
                print('[+] Clearing cookies')
                driver.get('chrome://settings/clearBrowserData')
                time.sleep(2)
                actions = ActionChains(driver) 
                actions.send_keys(Keys.TAB * 7 + Keys.ENTER).perform()
                time.sleep(5)
                print('[+] Cookies cleared\n')
                break

        except Exception as err:
            print(f'[-] Error "{err}", retrying...')
            time.sleep(30)
            i -= 1
            continue