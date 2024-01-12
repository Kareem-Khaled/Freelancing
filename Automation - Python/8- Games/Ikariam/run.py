import os
import json
import time
import zipfile
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from proxy_auth_plugin import manifest_json, background_js
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from proxy_config import USERNAME, PASSWORD, GUSER

urls = []
msg = 'Hello my friend'
sendFrom, sendTo = 0, 0
path = 'https://www.ikariam.com'

def save_links(driver, cur):
	global urls
	wr = -1
	while True:
		try:
			wr += 1
			if wr == 5:
				exit('Error, Please try again...')
			soup = BeautifulSoup(driver.page_source, 'lxml')
			trs = soup.find_all('tbody')[-1].find_all('tr')[1:]
			x = trs[0].find('td', class_='place bold').text.strip().replace(',', '')
			if x == cur.split(' - ')[0]:
				break
			time.sleep(1)
		except:
			print(f'error in save_links {x} - {cur.split(" - ")[0]}')
			time.sleep(1)
			wr += 1

	if wr == 5:
		exit('Error, Please try again...')

	for tr in trs:
		try:
			online = 1
			name = tr.find('td', class_='name')
			url = tr.find('td', class_='action').a['href']
			try:
				if 'gray' in name.a['class']:
					online = 0
			except:
				pass
			urls.append({
				'name': name.text.strip(),
				'id': url.split('=')[-1],
				'online': online
			})
		except:
			pass

	with open('urls.json', 'a', encoding='utf-8') as f:
		json.dump(urls, f, indent=4, ensure_ascii=False)

	urls = []

def get_links(driver):
	vis = []
	scroll = 0
	for i in range(1000):
		element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "dropDown_js_highscoreOffsetContainer")))
		lis = element.find_elements(By.TAG_NAME, 'li')[1:]
		flag = 0
		dd = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "js_highscoreOffsetContainer")))
		dd.find_element(By.CLASS_NAME, 'dropDownButton').click()
		time.sleep(1)
		# excute script on element to scroll to 0, scroll height
		driver.execute_script(f"arguments[0].scrollTo(0, {scroll});", element)
		scroll += 20

		for li in lis:			
			try:
				val = li.text.strip()
				if not len(val) or val in vis:
					continue
				print(f'val: {val}', flush=True)
				vis.append(val)
				li.click()
				time.sleep(1)
				flag = 1
				save_links(driver, val)
				break
			except Exception as e:
				print(e)
				time.sleep(5)

		if flag == 0:
			break

def send_messages(driver):
	global urls, msg, sendFrom, sendTo, path

	sendFrom = max(sendFrom, 0)
	sendTo = min(sendTo, len(urls))

	print(sendFrom, sendTo)
	print(f"->> Sending messages to players...")

	for i in range(sendFrom, sendTo):
		try:
			if not urls[i]['online']:
				continue

			driver.get(path + urls[i]['id'])
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//textarea[@id='js_msgTextConfirm']"))).send_keys(msg)
			time.sleep(0.3)
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='submit']"))).click()
			time.sleep(3)
			print(f"Message sent to ({i + 1}) - {urls[i]['name']}")
			if((i + 1) % 5 == 0):
				print('Going to sleep for 5 minutes...')
				time.sleep(5 * 60)
		except:
			pass

gmail = 'https://accounts.google.com/v3/signin/identifier?continue=https%3A%2F%2Fmail.google.com%2Fmail%2F&ifkv=ASKXGp3Rb9sTzYGet4uV2Nu27_Ylokr3Ip0txRUxd_IHEzaKs_n74r2px1KW-Txw190pWipmJfIdtA&rip=1&sacu=1&service=mail&flowName=GlifWebSignIn&flowEntry=ServiceLogin&dsh=S-2096534862%3A1701869154879444&theme=glif'
choice = 0
def run(use_proxy=False):
	global choice, path

	# Chrome options
	options = ChromeOptions()

	# proxy
	if use_proxy:
		pluginfile = 'proxy_auth_plugin.zip'
		with zipfile.ZipFile(pluginfile, 'w') as zp:
			zp.writestr("manifest.json", manifest_json)
			zp.writestr("background.js", background_js)
		options.add_extension(pluginfile)
	else:
		options.add_argument('--no-proxy-server')
		# remove that proxy extension
		options.extensions.clear()

	options.add_argument(f"user-data-dir=C:\\Users\\{GUSER}\\AppData\\Local\\Google\\Chrome\\User Data")
	user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.104 Safari/537.36"

	# options.add_argument('--headless')
	options.add_argument(f'user-agent={user_agent}')
	options.add_argument('--start-maximized')
	options.add_experimental_option('excludeSwitches', ['enable-logging'])

	print('->> logging...')
	with webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options) as driver:
		# driver.set_window_size(1920, 1080)
		# driver.get('https:/google.com')
		# input('Enter...')
		# driver.get(gmail)
		# WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))).send_keys(USERNAME)
		# WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Next')]"))).click()
		# WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))).send_keys(PASSWORD)
		# WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Next')]"))).click()
		# time.sleep(2)
		driver.get('https://lobby.ikariam.gameforge.com')
		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//li[contains(text(), 'Log in')]"))).click()
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Sign in with Google')]")))
			button = driver.find_element(By.CLASS_NAME, 'button-google')
			driver.execute_script("arguments[0].click();", button)
		except:
			pass
		print('->> logged in!')

		try:
			WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Last played')]"))).click()
		except Exception as e:
			print(e)
			exit('Error, Please try again later...')

		WebDriverWait(driver, 10).until(lambda driver: len(driver.window_handles) > 1)
		driver.switch_to.window(driver.window_handles[1])

		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Close')]"))).click()
		except: pass

		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Highscore')]"))).click()
		except: pass

		try:
			WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'OK')]"))).click()
		except: pass

		if choice == 1:
			print('->> Getting the players...')
			get_links(driver)
		else:
			path = driver.current_url.split('.com')[0] + '.com/index.php?view=sendIKMessage&receiverId='
			# print(path)
			send_messages(driver)
	
if __name__ == '__main__':
	choice = int(input('Press 1 to collect the urls and 2 to send messages: '))

	if choice == 2:
		sendFrom = int(input('Sending from player number: ')) - 1
		sendTo = int(input('To player number: ')) + 1

		with open('message.txt', 'r', encoding='utf-8') as f:
			msg = f.read()

		with open('urls.json', 'r', encoding='utf-8') as f:
			urls = json.load(f)

	else:
		if os.path.exists('urls.json'):
			os.remove('urls.json')

	run(True)