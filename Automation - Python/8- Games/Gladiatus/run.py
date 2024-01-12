import time
import zipfile
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from proxy_auth_plugin import manifest_json, background_js
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from proxy_config import GUSER

urls = set()
msg = 'Hello my friend'
def get_links(driver):
	global urls

	lst, valid = -1, 0
	for j in range(100):
		try:
			select_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, "//select[@name='d']")))
			select_object = Select(select_element)
			select_object.select_by_index(j)
			valid = j
		except:
			if valid == lst:
				break
			lst = valid

		for i in range(100):
			try:
				select_element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, "//select[@name='a']")))
				select_object = Select(select_element)
				select_object.select_by_index(i)
				WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, "ellipsis")))
				soup = BeautifulSoup(driver.page_source, 'lxml')
				tds = soup.find_all('td', {'class': 'ellipsis'})
				url = ''
				for td in tds:
					a = td.find('a')
					name = a.text.strip()
					sh = a['href'].split('sh=')[-1]
					url = f'https://s301-en.gladiatus.gameforge.com/game/index.php?mod=messages&submod=messageNew&profileName={name}&sh={sh}'
					urls.add(url)
			except: break

def send_messages(driver):
	global urls, msg

	print(f"->> Sending messages to {len(urls)} players...")

	for url in urls:
		try:
			driver.get(url)
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//textarea[@id='message']"))).send_keys(msg)
			time.sleep(0.3)
			submit_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.NAME, "sent")))
			action_chains = ActionChains(driver)
			action_chains.click(submit_button).perform()
		except:
			pass

def run(use_proxy=False):
	# Chrome options
	options = ChromeOptions()
	if use_proxy:
		pluginfile = 'proxy_auth_plugin.zip'
		with zipfile.ZipFile(pluginfile, 'w') as zp:
			zp.writestr("manifest.json", manifest_json)
			zp.writestr("background.js", background_js)
		options.add_extension(pluginfile)
	else:
		options.add_argument('--no-proxy-server')

	options.add_argument(f"user-data-dir=C:\\Users\\{GUSER}\\AppData\\Local\\Google\\Chrome\\User Data")
	user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.104 Safari/537.36"

	# options.add_argument('--headless')
	options.add_argument(f'user-agent={user_agent}')
	options.add_argument('--start-maximized')
	options.add_experimental_option('excludeSwitches', ['enable-logging'])

	print('->> logining...')
	with webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options) as driver:
		# driver.set_window_size(1920, 1080)
		# driver.get('https:/google.com')
		# input('Enter...')
		driver.get('https://lobby.gladiatus.gameforge.com')
		# input('Enter...')
		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//li[contains(text(), 'Log in')]"))).click()
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Sign in with Google')]")))
			button = driver.find_element(By.CLASS_NAME, 'button-google')
			driver.execute_script("arguments[0].click();", button)
		except Exception as e:
			pass
		print('->> logged in!')
		# WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email"))).send_keys('lindsaywiegand79@gmail.com')
		# password = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "password")))
		# password.send_keys('Jordanair1')
		# password.send_keys(Keys.ENTER)

		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Last played')]"))).click()
		except Exception as e:
			print(e)
			exit('Error, Please try again later...')

		print('->> logged in!')
		WebDriverWait(driver, 10).until(lambda driver: len(driver.window_handles) > 1)
		driver.switch_to.window(driver.window_handles[1])

		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@value='Collect Bonus']"))).click()
		except: pass

		print('->> Getting the players...')

		WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Highscore')]"))).click()

		get_links(driver)

		WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Dungeons')]"))).click()
		WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Dungeon - 7 Day Highscore')]"))).click()

		get_links(driver)

		send_messages(driver)

if __name__ == '__main__':
	with open('message.txt', 'r', encoding='utf-8') as f:
		msg = f.read()

	run(True)
