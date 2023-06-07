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

	# options.add_argument("user-data-dir=C:\\Users\\mtala\\AppData\\Local\\Google\\Chrome\\User Data")
	user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.104 Safari/537.36"

	# options.add_argument('--headless')
	options.add_argument(f'user-agent={user_agent}')
	options.add_argument('--start-maximized')
	options.add_experimental_option('excludeSwitches', ['enable-logging'])

	print('->> logining...')
	with webdriver.Chrome(ChromeDriverManager().install() , options = options) as driver:
		# driver.set_window_size(1920, 1080)
		driver.get('https:/google.com')
		input('Enter...')


if __name__ == '__main__':
	run(True)
