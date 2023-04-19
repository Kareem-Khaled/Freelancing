import time
import random
import asyncio
import warnings
import telegram
from selenium import webdriver
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def save_slots(slots):
    slots = "\n".join(slots)
    with open('slots.txt', 'w') as f:
        f.write(slots)

def same_slots(new_slots):
    try:
        with open('slots.txt', 'r') as f:
            old_slots = f.read().splitlines()

        for value in new_slots:
            if value not in old_slots:
                save_slots(new_slots)
                return False

        return True
    except:
        save_slots(new_slots)
        return False

warnings.filterwarnings("ignore", category = DeprecationWarning) 
bot = telegram.Bot(token='6220637553:AAH55JhQnl9e-93191bfDEQJVGQn_KNpO2k')
def send_telegram_message(message):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.send_message(chat_id='-977055796', text=message))

def less_than_31_days(date_str):
    # Convert date string to a datetime object
    date_obj = datetime.strptime(f"{date_str}/{datetime.now().year}", "%d/%m/%Y")

    # Get tomorrow's date
    tomorrow = datetime.now().date() + timedelta(days=1)

    # Calculate the difference between the dates in days
    diff_days = (date_obj.date() - tomorrow).days

    # Check if the difference is less than 31 days
    if diff_days < 31:
        return True
    else:
        return False

def monitor_site():
    options = Options()
    options.headless = True
    # options.add_experimental_option('excludeSwitches', ['enable-logging']) # remove warnings

    with webdriver.Firefox(options=options) as driver:
        driver.set_window_size(1440, 900)
        driver.get("https://web.theopenstage.it/home")
        print("Opened website", flush=True)
        try:
            # Check if login form is present
            WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.TAG_NAME, "input")))
            input_tag = driver.find_elements(By.TAG_NAME, "input")

            # Login
            input_tag[0].send_keys("tsimurshved2@gmail.com")
            input_tag[1].send_keys("Shved23")
            input_tag[1].send_keys(Keys.RETURN)
            print("Logged in", flush=True)
        except:
            # Login form not present, already logged in
            print("Already logged in", flush=True)

        # Go to booking page
        time.sleep(random.randint(1, 3))
        driver.get("https://web.theopenstage.it/booking/cities/21/areas/20/places")
        print("Navigated to booking page", flush=True)

        # Look for div with specified h3 text
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//div[@class='stage-description']")))
        divs = driver.find_elements(By.XPATH, "//div[@class='stage-description']")
        for div in divs:
            h3 = div.find_element(By.TAG_NAME, "h3")
            if h3.text == "P006 Piazza Duomo":
                
                # Found the div
                print("Found div with P006 Piazza Duomo", flush=True)
                
                # Click on "Scegli il tuo slot" button
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//button[contains(text(),'Scegli il tuo slot')]")))
                button = div.find_element(By.XPATH, "//button[contains(text(),'Scegli il tuo slot')]")
                button.click()
                print("Clicked on Scegli il tuo slot button", flush=True)

        # Wait for popup to appear
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//div[@class='modal-card']")))
        print("Popup appeared")

        # Click on "Date disponibili" button
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//ng-select[@placeholder='Date disponibili']")))
        date_button = driver.find_element(By.XPATH, "//ng-select[@placeholder='Date disponibili']")
        date_button.click()
        print("Clicked on Date disponibili button")

        # Get list of available dates
        available_dates = []
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//span[@class='ng-option-label']")))
        options = driver.find_elements(By.XPATH, "//span[@class='ng-option-label']")
        for option in options:
            date_text = option.text
            available_dates.append(date_text)

        # Writing available dates into slots.txt if it's new
        if same_slots(available_dates):
            print('The slots are still the same as before.')
            return
        
        # Send message via Telegram bot with available dates within the next month that include "sab" or "dom"
        message = "Postazioni libere dal giorno attuale a massimo un mese in avanti che includano 'sab' o 'dom':"
        for date in available_dates:
            [day, date_] = date.split(',')[0].split(' ')
            start_time = date.split(',')[1].split(' - ')[0]
            if (day == "sab" or day == "dom") and (start_time == '11:00' or start_time == '14:00' or start_time == '17:00') and (less_than_31_days(date_)):
                message += f"{date}"
                print(f"Message to send: {message}")
                send_telegram_message(message)
                return
        
        # Send no slots message via Telegram bot
        print("Send no slots message")
        send_telegram_message('No interesting slots')

if __name__ == '__main__':
    while True:
        try:
            monitor_site()
        except Exception as e:
            send_telegram_message(f"Error: {e}")
        
        # Wait random amount of time between 30 and 90 seconds before starting again
        print('Waiting...')
        time.sleep(random.randint(30, 90))