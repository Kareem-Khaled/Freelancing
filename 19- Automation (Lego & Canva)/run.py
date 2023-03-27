import time
import warnings
import clipboard
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from msedge.selenium_tools import Edge, EdgeOptions
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.microsoft import EdgeChromiumDriverManager  

options = EdgeOptions()
options.use_chromium = True
options.add_argument('--start-maximized')
warnings.filterwarnings("ignore", category = DeprecationWarning) 
options.add_experimental_option('excludeSwitches', ['enable-logging']) 
options.add_argument("user-data-dir=C:\\Users\\<your username>\\AppData\\Local\\Microsoft\\Edge\\User Data")
driver = Edge(executable_path=EdgeChromiumDriverManager().install(), options=options)

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
    buttons = driver.find_elements(By.TAG_NAME, 'button')

    for button in buttons:
        if '+ Add page' in button.text:
            btn = button
            break

    for url in imges:
        clipboard.copy(url)
        btn.click()
        time.sleep(delay)
        actions = ActionChains(driver)
        actions.key_down(Keys.SHIFT)
        actions.send_keys(Keys.INSERT)
        actions.key_up(Keys.SHIFT)
        actions.perform()
        time.sleep(delay)

    print('->> Done!!!')
    time.sleep(delay)
    driver.close()

if __name__ == '__main__':
    url = input("->> Please enter the Lego url: ")
    run(url)