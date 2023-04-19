import json
import time
import warnings
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

options = ChromeOptions()
warnings.filterwarnings("ignore", category = DeprecationWarning) 
options.add_experimental_option('excludeSwitches', ['enable-logging']) # remove warnings
options.add_argument('--start-maximized')
settings = {
    "recentDestinations": [{
        "id": "Save as PDF",
        "origin": "local",
        "account": "",
    }],
    "selectedDestinationId": "Save as PDF",
    "version": 2
}
prefs = {'printing.print_preview_sticky_settings.appState': json.dumps(settings)}
options.add_experimental_option('prefs', prefs)
options.add_argument('--kiosk-printing')
driver = webdriver.Chrome(ChromeDriverManager().install(), options = options)

def run():
    # driver.get('https://login.yahoo.com')
    url = 'https://finance.yahoo.com/quote/MSFT?p=MSFT&.tsrc=fin-srch' or input("->> Please login first the enter the url: ")
    driver.get(url)
    time.sleep(3)
    driver.execute_script('window.print();')
    driver.quit()

if __name__ == '__main__':
    run()