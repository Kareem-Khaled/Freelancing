import time
import random
import warnings
from selenium import webdriver
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService

def save_slots(slots, name):
    slots = "\n".join(slots)
    with open(f'{name}.txt', 'w') as f:
        f.write(slots)

def same_slots(new_slots, name):
    try:
        with open(f'{name}.txt', 'r') as f:
            old_slots = f.read().splitlines()

        if set(new_slots) == set(old_slots):
            return True
        else:
            save_slots(new_slots, name)
            return False
    except:
        save_slots(new_slots, name)
        return False

warnings.filterwarnings("ignore", category = DeprecationWarning)

def less_than_31_days(date_str):
    # Convert date string to a datetime object
    date_obj = datetime.strptime(f"{date_str}/{datetime.now().year}", "%d/%m/%Y")

    # Get tomorrow's date
    tomorrow = datetime.now().date() + timedelta(days=1)

    if tomorrow.month > date_obj.month:
        date_obj = datetime.strptime(f"{date_str}/{datetime.now().year + 1}", "%d/%m/%Y")

    # Calculate the difference between the dates in days
    diff_days = (date_obj.date() - tomorrow).days

    # Check if the difference is less than or equal to 31 days
    if diff_days <= 31:
        return True
    else:
        return False

def get_slots(driver, Data, qu, stop_event, num):
    while num and not stop_event.is_set():
        
        ret = findIds(driver, Data)
        # print(ret)
        # Click on "Scegli il tuo slot" button
        for data in ret:
            qu.put(f"Checking {data[1]}...")
            driver.refresh()
            place_div = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, data[0])))
            button = WebDriverWait(place_div, 10).until(EC.visibility_of_element_located((By.XPATH, "./div/button[contains(text(),'Scegli il tuo slot')]")))
            button.click()
            print("Clicked on Scegli il tuo slot button")
            qu.put("Clicked on Scegli il tuo slot button")
            
            # Wait for popup to appear
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//div[@class='modal-card']")))
            print("Popup appeared")
            qu.put("Popup appeared")

            # Click on "Date disponibili" button
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "ng-select-clearable")))
            date_button = driver.find_element(By.CLASS_NAME, "ng-select-clearable")

            # date_button.click()
            ActionChains(driver).move_to_element(date_button).click().perform()
            print("Clicked on Date disponibili button")
            qu.put("Clicked on Date disponibili button")

            # Get list of available dates
            available_dates = []
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//span[@class='ng-option-label']")))
            options = driver.find_elements(By.XPATH, "//span[@class='ng-option-label']")
            for option in options:
                date_text = option.text
                available_dates.append(date_text)
                
            # Writing available dates into slots.txt if it's new
            if same_slots(available_dates, data[1]):
                print(f'{data[1]} The slots are still the same as before.')
                qu.put(f'{data[1]} The slots are still the same as before.')
                continue

            # Send message via Telegram bot with available dates within the next month that include "sab" or "dom"
            send = False
            message = data[1] + ' - '
            for date in available_dates:
                [day, date_] = date.split(',')[0].split(' ')
                start_time = date.split(',')[1].split(' - ')[0]
                if (day == "sab" or day == "dom") and (start_time == '11:00' or start_time == '14:00' or start_time == '17:00') and (less_than_31_days(date_)):
                    message += f"{date}"
                    print(f"Message to send: {message}")
                    qu.put(f"Message to send: {message}")
                    qu.put(f"TMSG {message}")
                    send = True
                    # save_slots(available_dates, data[1])
                    # send_telegram_message(message)
                    break
                    
            # Send no slots message via Telegram bot
            if not send:
                print(f'{data[1]} No interesting slots')
                qu.put(f'{data[1]} No interesting slots')
                # qu.put(f"TMSG {data[1]} No interesting slots")
                # send_telegram_message('No interesting slots')

        t = random.randint(10, 45)
        for tt in range(t // 2):
            if stop_event.is_set():
                qu.put("Stopping...")
                print("Stopping...")
                return
            print(f'Waiting... {t - tt * 2}s')
            qu.put(f'Waiting... {t - tt * 2}s')
            time.sleep(2)

        num -= 1
        driver.refresh()

def findIds(driver, data):
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.TAG_NAME, "h3")))
    h3_elements = driver.find_elements(By.TAG_NAME, "h3")

    temp = {}
    for element in h3_elements:
        for da in data:
            if da in element.text:
                if da in temp and "ME" not in element.text: continue
                parent_div = element.find_element(By.XPATH, "..").find_element(By.XPATH, "..")
                id = parent_div.get_attribute("id")
                temp[da] = id
                break
    ret = []
    for t in temp:
        ret.append([temp[t], t])

    # print(ret)
    return ret

def monitor_site(data, qu, stop_event, num):
    # options = Options()
    # options.headless = True
    # with webdriver.Firefox(options=options, executable_path='/usr/bin/geckodriver') as driver:
    
    options = ChromeOptions()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.104 Safari/537.36"
    options.add_argument('--headless')
    options.add_argument(f'user-agent={user_agent}')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    with webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options) as driver:
        driver.set_window_size(1440, 900)
        driver.get("https://web.theopenstage.it/home")
        print("Opened website", flush=True)
        qu.put("Opened website")
        try:
            # Check if login form is present
            WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.TAG_NAME, "input")))
            input_tag = driver.find_elements(By.TAG_NAME, "input")

            # Login
            input_tag[0].send_keys("katephoebe84@gmail.com")
            input_tag[1].send_keys("openstage1")
            input_tag[1].send_keys(Keys.RETURN)
            print("Logged in", flush=True)
            qu.put("Logged in")
        except:
            # Login form not present, already logged in
            print("Already logged in", flush=True)
            qu.put("Already logged in")

        # Go to booking page
        time.sleep(random.randint(1, 3))
        driver.get("https://web.theopenstage.it/booking/cities/21/areas/20/places")
        print("Navigated to booking page", flush=True)
        qu.put("Navigated to booking page")

        # findIds(driver, data)
        get_slots(driver, data, qu, stop_event, num)

if __name__ == '__main__':
    pass
    # monitor_site(["P006", "P003", "P041"], print_queue, 3)

    # while True:
    #     try:
    #         monitor_site()
    #     except Exception as e:
    # send_telegram_message(f"Error: {e}")
        
    #     print('Waiting...')
    #     time.sleep(random.randint(10, 45))