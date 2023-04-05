import time
import warnings
import clipboard
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains

options = ChromeOptions()
warnings.filterwarnings("ignore", category = DeprecationWarning) 
options.add_experimental_option('excludeSwitches', ['enable-logging']) # remove warnings
options.add_argument("user-data-dir=C:\\Users\\KeMo\\AppData\\Local\\Google\\Chrome\\User Data")
options.add_argument('--start-maximized')
driver = webdriver.Chrome(ChromeDriverManager().install(), options = options)

def run(link):
    driver.get(link)
    soup = BeautifulSoup(driver.page_source, 'lxml')
    imges = set()
    imgSources = soup.find_all('source', {'type' :"image/webp"})
    for imgs in imgSources:
        if '.png' not in imgs['srcset']: continue
        imges.add(imgs['srcset'].split('.png')[0] + '.png')

    url = input("->> Please enter the Canva project url: ")
    delay = int(input("->> Please enter the delay in secondes: "))

    driver.get(url)
    input('->> Press enter when you are ready...')
    actions = ActionChains(driver)
    for url in imges:
        clipboard.copy(url)
        # actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        # actions.send_keys(Keys.DELETE).perform()
        time.sleep(delay)
        actions.key_down(Keys.CONTROL).send_keys("v").perform()
        actions.key_up(Keys.CONTROL).perform()

        buttons = driver.find_elements(By.TAG_NAME, 'button')
        for button in buttons:
            if '+ Add page' in button.text:
                button.click()
                break
    
    print('->> Done!!!')
    driver.close()

if __name__ == '__main__':
    url = input("->> Please enter the Lego url: ")
    run(url)