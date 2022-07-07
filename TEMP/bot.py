import os
import sys
import time
import json
import string    
import random
import requests
import itertools
import subprocess
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


def get_path(additional_path, addition_name):
    path_to_file = os.path.join(PARENT_PATH, additional_path)
    print(f'{addition_name} Path: {path_to_file}')

    return path_to_file

port = input("Please enter your multilogin port: ")

def run_profile(mla_profile_id):
    mla_url = 'http://127.0.0.1:'+ str(port) +'/api/v1/profile/start?automation=true&profileId=' + mla_profile_id
    resp = requests.get(mla_url)
    j = json.loads(resp.content)
    driver = webdriver.Remote(command_executor=j['value'])
    return driver

def create_profile():
    browser = ['mimic', 'stealthfox']
    os = ['win', 'mac', 'lin']
    name = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 50))    
    x = {
        "name": name,
        "browser": random.choice(browser),
        "os": random.choice(os),
    }
    header = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    url = "http://localhost:"+ str(port) +"/api/v2/profile"
    req = requests.post(url, data=json.dumps(x), headers=header)

    return json.loads(req.content).get("uuid")

# def delete_profile(mla_profile_id):
#     url = "http://localhost:"+ str(port) +"/api/v2/profile/" + mla_profile_id
#     resp = requests.delete(url)
#     print(resp)
#     print("profile " + mla_profile_id + " is deleted successfully")

# def delete_profile_by_name(profile_name):
#     profile_list = list_profiles()
#     for i in profile_list:
#         if i['name'] == profile_name:
#             delete_profile(i['uuid'])

# def delete_all_profiles():
#     for i in (get_profile_ids()):
#         delete_profile(i)
#     print("\nDone deleting all profiles")

def list_profiles():
    url = "http://localhost:"+ str(port) +"/api/v2/profile"
    resp = requests.get(url)
    resp_json = json.loads(resp.content)
    return resp_json

def get_profile_ids():
    profile_list = list_profiles()
    profile_ids = []
    for i in profile_list:
        profile_ids.append(i['uuid'])
    return profile_ids

def bulk_create(amount_of_profiles):
    for _ in itertools.repeat(None, amount_of_profiles):
        create_profile()
    print(amount_of_profiles.__str__() + " profiles created successfully!")

def get_proxies():
    file_path = "proxy.txt"
    with open(file_path) as file:
        proxies = json.load(file)
        return proxies

def update_profile_proxy(profile_id, proxy):
    url = 'http://localhost:'+ str(port) +'/api/v2/profile/' + profile_id
    header = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {
        "network": {
            "proxy": {
                "type": proxy['type'],
                "host": proxy['host'],
                "port": proxy['port'],
                "username": proxy['username'],
                "password": proxy['password']
            }
        }
    }
    r = requests.post(url, json.dumps(data), headers=header)
    print("#", end='', flush=True)


# def update_profile_group(profile_id, group_id):
#     url = 'http://localhost:'+ str(port) +'/api/v2/profile/' + profile_id
#     header = {
#         "accept": "application/json",
#         "Content-Type": "application/json"
#     }
#     data = {
#         "group": group_id
#     }
#     r = requests.post(url, json.dumps(data), headers=header)
#     print(r.status_code)


# def move_profiles_to_group(group_id):
#     profile_ids = get_profile_ids()
#     for i in profile_ids:
#         update_profile_group(i, group_id)


# def change_proxies():
#     profile_ids = get_profile_ids()
#     proxies = get_proxies()
#     amount_of_proxies = len(proxies['proxies']['proxy'])
#     for i in range(amount_of_proxies):
#         update_profile_proxy(profile_ids[i], proxies['proxies']['proxy'][i])
#     print('The proxies have been assigned')


# def import_cookies(profile_id):
#     url = 'http://localhost.multiloginapp.com:'+ str(port) +'/api/v1/profile/cookies/import/webext?profileId=' + profile_id
#     header = {
#         "accept": "*/*",
#         "Content-Type": "text/plain"
#     }
#     file_path = 'ENTER_THE_FILE_PATH_HERE'  # the file should contain cookies in JSON format
#     with open(file_path) as file:
#         cookies = json.load(file)
#         resp = requests.post(url, data=json.dumps(cookies), headers=header)
#         print(resp.content)
#         print('cookie import finished')

if __name__ == '__main__':
    PARENT_PATH = os.path.dirname(os.path.abspath(__file__))

    print('File Paths:')
    emails_file_path = get_path(r'EMAILs.txt', 'Emails file')
    links_file_path = get_path(r'LINKs.txt', 'Links file')
    print()

    print('File Data:')
    emails = get_emails()
    links = get_links()

    print(f'Multilogin profiles count: {len(get_profile_ids())}')
    print('\n-----------------------------------------------------------------------------\n')

    number_of_iterations = int(input('[!] Number of Loops:\n'))
    print()
    delay = input('[!] Delay between links (e.g 40-60):\n').split('-')
    print()
    email_usage = int(input('[!] Number of times an email is used:\n'))
    print()
    newBrowsers = int(input('[!] Number of new multilogin profiles you want to create:\n'))
    print()
    browser_usage = int(input('[!] Number of multilogin profiles you want to use:\n'))
    print()
    if newBrowsers:
        print(f"Creating {newBrowsers} new multilogin profiles...", flush=True)
        bulk_create(newBrowsers)
        # profile_ids = get_profile_ids()
        # prox = get_proxies()
        # print(f"Editing proxy for all profiles...", flush=True)
        # for id in profile_ids:
        #      update_profile_proxy(id, prox)
        # print(f"\nProfiles ready to use!", flush=True)

    print('[+] Bot started.\n')

    e = 0
    brws = 0
    email = ''
    profile_ids = get_profile_ids()
    browser_usage = min(browser_usage, len(profile_ids))
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

                    driver = run_profile(profile_ids[brws])
                    print(f'[{i}] Working with: {link}, browser number: [{brws}]')
                    time.sleep(wait)
                    driver.get(link)

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

                    try:
                        wait = random.randint(int(delay[0]), int(delay[1]))
                    except ValueError:
                        wait = random.randint(int(delay[1]), int(delay[0]))
                    print(f'\t- Waiting {wait} seconds...\n')
                    driver.quit()
                    time.sleep(wait)
                    print('[+] Changing the browser')
                    brws += 1
                    if brws == browser_usage:
                        brws = 0
                    break

            except Exception as err:
                print(f'[-] Error "{err}", retrying...')
                time.sleep(30)
                i -= 1
                continue