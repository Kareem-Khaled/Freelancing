import os
import time
from bs4 import BeautifulSoup
from selenium.webdriver import Chrome, ChromeOptions
import warnings
import xlsxwriter

warnings.filterwarnings("ignore", category=DeprecationWarning)
options = ChromeOptions()
options.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = Chrome(executable_path = os.getcwd() + '\chromedriver', options=options)

website = "http://179.124.10.235/HBconselhos/pgs/ConsultaMembroConselho.aspx?secao=Busca%20de%20Advogados"
try:
    driver.get(website)
    src = driver.page_source
    soup = BeautifulSoup(src, 'lxml')
    captcha = input('- Please enter captcha text:-\n')
    captchaText = driver.find_element_by_id("m_CaptchaText")
    captchaText.send_keys(captcha)
    searchBtb = driver.find_element_by_id("A2")
    searchBtb.click()
    time.sleep(15)
except:
    print('=== there is a problem in the website please restart the app ===')

links = []
page = 1
wr = 0
print("- Getting all the pages...")
while page:
    try:
        if page != 1 and page % 10 == 1:
            driver.find_elements_by_link_text('...')[-1].click()
        elif page != 1:
            driver.find_element_by_link_text(str(page)).click()

        src = driver.page_source
        soup = BeautifulSoup(src, 'lxml')
        TDS = soup.find('div',{'id':'m_dvGridPessoa'}).find('table').findAll('td')
        for TD in TDS:
            a = TD.find('a')
            if a == None or not a.has_attr('onclick'):
                continue   
            l = str(a['onclick']).find('&') + 1
            r = str(a['onclick']).find(')') + 1
            link = 'http://179.124.10.235/HBconselhos/pgs/InformacoesEnderecoWeb.aspx?'+str(a['onclick'])[l:r]
            links.append(link)
        print(f"- page: {page} doneee.")
        page += 1
    except:
        print("hmmmmmm.")
        wr += 1
        if wr >= 50:
            break

print(f"- Scrabing the {page} pages...")
workbook = xlsxwriter.Workbook('link2_data.xlsx')
bold = workbook.add_format({'bold': True})
worksheet = workbook.add_worksheet("data")
row = 0
col = 0
wr = 0
for link in links:
    try:
        driver.get(link)
        src = driver.page_source
        soup = BeautifulSoup(src, 'lxml')
        div = soup.find('div',{'id':'DivEnderecoProfissional'})
        if div == None:
            continue
        tds = div.find('table').findAll('td')
        dic = {}
        key = ''
        for td in tds:
            inp = td.find('input')
            if inp != None:
                if inp.has_attr('value'):
                    dic[key] = str(inp['value']) 
                else:
                    dic[key] = "N/A"
            else:
                key = td.text.strip()

        if dic['Telefone'] != "N/A":
            dic['Telefone'] = '+55' + dic['Telefone'].replace('(','').replace(')','').replace('-','').replace(' ','')

        if dic['Celular'] != "N/A":
            dic['Celular'] = '+55' + dic['Celular'].replace('(','').replace(')','').replace('-','').replace(' ','')
        
        if row == 0:
            for key in (dic):
                worksheet.write(row, col, key, bold)
                col += 1
            row += 1

        col = 0
        for key in (dic):
            worksheet.write(row, col, dic[key])
            col += 1
        row += 1
        print(f"- new item inserted {dic['Nome']}")
    except:
        print("hmmmmmm..")
        wr += 1
        if wr >= 50:
            break

print("Done :)")
workbook.close()
driver.quit()
