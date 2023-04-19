import warnings
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


class MyPass(unittest.TestCase):
    def setUp(self):
        options = ChromeOptions()
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        options.add_experimental_option(
            'excludeSwitches', ['enable-logging'])  # remove warnings
        options.add_argument("--disable-notifications")  # hide pop-ups
        driver = webdriver.Chrome(
            ChromeDriverManager().install(), options=options)
        driver.maximize_window()
        self.driver = driver

    def solve(self, tag, target):
        driver = self.driver
        driver.find_element(By.TAG_NAME, tag).click()
        lis = driver.find_elements(By.TAG_NAME, 'li')
        actions = ActionChains(driver)
        for li in lis:
            if li.text == target:
                actions.move_to_element(li).click().perform()
                break

    def test_AUD(self):
        driver = self.driver
        driver.get('https://automation01.sit.mypassglobal.com/login')
        WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ng-untouched")))

        driver.find_elements(
            By.CLASS_NAME, 'ng-untouched')[1].send_keys('rkamran+u1@mypassglobal.com')

        driver.find_elements(
            By.CLASS_NAME, 'ng-untouched')[2].send_keys('Pakistan123@')

        driver.find_element(By.CLASS_NAME, 'accent').click()

        WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.CLASS_NAME, "menu")))

        driver.get(
            'https://automation01.sit.mypassglobal.com/secure/settings/manage-subscription')

        WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.CLASS_NAME, "accent")))

        driver.find_element(By.CLASS_NAME, 'accent').click()

        WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.ID, "businessName")))

        tmp = driver.find_element(By.ID, 'businessName')
        tmp.send_keys(Keys.LEFT_CONTROL + 'a')
        tmp.send_keys('Babar Khan')

        tmp = driver.find_element(By.ID, 'email')
        tmp.send_keys(Keys.LEFT_CONTROL + 'a')
        tmp.send_keys('babarkhan@mypassglobal.com')

        self.solve('lib-select-input', 'AUD')
        self.solve('lib-country-picker-input', 'Australia\n+61')

        tmp = driver.find_elements(By.TAG_NAME, 'input')[2]
        tmp.send_keys(Keys.LEFT_CONTROL + 'a')
        tmp.send_keys('a')

        WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.TAG_NAME, "h5")))
        tmp = driver.find_elements(
            By.CLASS_NAME, "list")[-1].find_element(By.TAG_NAME, 'li').click()

        driver.find_elements(By.CLASS_NAME, 'accent')[-1].click()

        ####### second #######

        WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.CLASS_NAME, "start")))

        self.solve('lib-select-input', '5 to 19 personnel')

        driver.find_element(By.CLASS_NAME, 'light.ng-star-inserted').click()
        driver.find_elements(By.TAG_NAME, 'button')[-1].click()

        ####### third #######

        WebDriverWait(driver, 50).until(
            EC.presence_of_element_located((By.CLASS_NAME, "total")))

        txt = driver.find_element(By.CLASS_NAME, 'total').text
        self.assertIn('AUD', txt)

    def tearDown(self):
        self.driver.quit()


if __name__ == '__main__':
    unittest.main()
