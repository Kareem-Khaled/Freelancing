import threading
import xlsxwriter
from bs4 import BeautifulSoup
from requests_html import HTMLSession
from concurrent.futures import ThreadPoolExecutor

urls = [
'https://www.shopcreativekids.com/judaica/rosh-hashanah/',
'https://www.shopcreativekids.com/seasonal/party/ribbon/',
'https://www.shopcreativekids.com/judaica/holiday/purim/',
'https://www.shopcreativekids.com/judaica/holiday/pesach/',
'https://www.shopcreativekids.com/judaica/holiday/succos/',
'https://www.shopcreativekids.com/judaica/holiday/shavous/',
'https://www.shopcreativekids.com/judaica/holiday/chanukah/',
'https://www.shopcreativekids.com/judaica/hebrew-education/',
'https://www.shopcreativekids.com/seasonal/graduation/',
'https://www.shopcreativekids.com/seasonal/party/balloons/',
'https://www.shopcreativekids.com/seasonal/party/bags/',
'https://www.shopcreativekids.com/seasonal/party/cellophane-rolls/',
'https://www.shopcreativekids.com/seasonal/party/face-paint/',
'https://www.shopcreativekids.com/seasonal/party/tissue-paper/',
'https://www.shopcreativekids.com/seasonal/party/hats/',
'https://www.shopcreativekids.com/seasonal/party/streamer/',
'https://www.shopcreativekids.com/seasonal/party/mylar-rolls/',
'https://www.shopcreativekids.com/seasonal/party/supplies/',
'https://www.shopcreativekids.com/seasonal/music/',
'https://www.shopcreativekids.com/seasonal/shabbos/',
'https://www.shopcreativekids.com/seasonal/alef-bet/',
'https://www.shopcreativekids.com/seasonal/lag-bomer/',
'https://www.shopcreativekids.com/seasonal/judaica-misc/',
'https://www.shopcreativekids.com/toys-and-games/prizes/keychain/',
'https://www.shopcreativekids.com/toys-and-games/prizes/balls/',
'https://www.shopcreativekids.com/toys-and-games/prizes/erasers/',
'https://www.shopcreativekids.com/toys-and-games/prizes/pens-and-pencils/',
'https://www.shopcreativekids.com/toys-and-games/prizes/jewelry/',
'https://www.shopcreativekids.com/toys-and-games/prizes/coin-purse/',
'https://www.shopcreativekids.com/toys-and-games/prizes/bubbles/',
'https://www.shopcreativekids.com/toys-and-games/prizes/animals/',
'https://www.shopcreativekids.com/toys-and-games/prizes/cut-outs/',
'https://www.shopcreativekids.com/toys-and-games/prizes/sunglasses/',
'https://www.shopcreativekids.com/toys-and-games/prizes/whistle/',
'https://www.shopcreativekids.com/toys-and-games/puzzles/',
'https://www.shopcreativekids.com/toys-and-games/pretend-play/',
'https://www.shopcreativekids.com/toys-and-games/books/activity/',
'https://www.shopcreativekids.com/toys-and-games/books/readers/',
'https://www.shopcreativekids.com/toys-and-games/books/language-arts/',
'https://www.shopcreativekids.com/toys-and-games/books/handwriting/',
'https://www.shopcreativekids.com/toys-and-games/books/mathaematics/',
'https://www.shopcreativekids.com/toys-and-games/books/science/',
'https://www.shopcreativekids.com/toys-and-games/books/teacher-resources/',
'https://www.shopcreativekids.com/toys-and-games/books/how-to/',
'https://www.shopcreativekids.com/toys-and-games/jewish/',
'https://www.shopcreativekids.com/toys-and-games/educational-games/',
'https://www.shopcreativekids.com/toys-and-games/flowers/',
'https://www.shopcreativekids.com/paper/stationery/',
'https://www.shopcreativekids.com/paper/glossy-board/',
'https://www.shopcreativekids.com/paper/metallic-foil-board/',
'https://www.shopcreativekids.com/paper/large-poster-board/',
'https://www.shopcreativekids.com/paper/oak-tag/',
'https://www.shopcreativekids.com/paper/construction-paper/',
'https://www.shopcreativekids.com/paper/cut-outs/',
'https://www.shopcreativekids.com/paper/metallic-foil-paper/',
'https://www.shopcreativekids.com/paper/glossy-paper/',
'https://www.shopcreativekids.com/paper/tag-board/',
'https://www.shopcreativekids.com/paper/card-stock/',
'https://www.shopcreativekids.com/kids-crafts/wood-crafts/',
'https://www.shopcreativekids.com/kids-crafts/sand-art/',
'https://www.shopcreativekids.com/kids-crafts/diy/',
'https://www.shopcreativekids.com/kids-crafts/paint/markers/',
'https://www.shopcreativekids.com/kids-crafts/paint/do-a-dot/',
'https://www.shopcreativekids.com/kids-crafts/scrapbooking/',
'https://www.shopcreativekids.com/kids-crafts/perler-beads/',
'https://www.shopcreativekids.com/kids-crafts/craft-kits/crystal-crafts/',
'https://www.shopcreativekids.com/kids-crafts/knitting-and-yarn/',
'https://www.shopcreativekids.com/kids-crafts/beading/rhinestones/',
'https://www.shopcreativekids.com/kids-crafts/kits/',
'https://www.shopcreativekids.com/kids-crafts/modeling-clay/',
'https://www.shopcreativekids.com/kids-crafts/hardware/',
'https://www.shopcreativekids.com/kids-crafts/supplies/',
'https://www.shopcreativekids.com/stickers/aleph-bais/rashi/',
'https://www.shopcreativekids.com/stickers/animals/',
'https://www.shopcreativekids.com/stickers/shabbos/',
'https://www.shopcreativekids.com/stickers/holidays/rosh-hashana/',
'https://www.shopcreativekids.com/stickers/food/',
'https://www.shopcreativekids.com/stickers/eyes/',
'https://www.shopcreativekids.com/stickers/stars/',
'https://www.shopcreativekids.com/stickers/shapes/',
'https://www.shopcreativekids.com/stickers/labels/',
'https://www.shopcreativekids.com/stickers/transportation/',
'https://www.shopcreativekids.com/stickers/flowers/',
'https://www.shopcreativekids.com/stickers/smiles/',
'https://www.shopcreativekids.com/stickers/alphabet/',
'https://www.shopcreativekids.com/stickers/rhinestones/',
'https://www.shopcreativekids.com/stickers/foam/',
'https://www.shopcreativekids.com/stickers/motivational/english/',
'https://www.shopcreativekids.com/stickers/motivational/hebrew/',
'https://www.shopcreativekids.com/stickers/seasons/',
'https://www.shopcreativekids.com/stickers/mazel-tov/',
'https://www.shopcreativekids.com/stickers/sticker-puzzle/',
'https://www.shopcreativekids.com/stickers/birthday/',
'https://www.shopcreativekids.com/stickers/torahs/',
'https://www.shopcreativekids.com/stickers/scented/',
'https://www.shopcreativekids.com/stickers/sticker-book/',
'https://www.shopcreativekids.com/stickers/money/',
'https://www.shopcreativekids.com/stickers/stick-a-licks/',
'https://www.shopcreativekids.com/stickers/hearts/',
'https://www.shopcreativekids.com/drawing/pads/',
'https://www.shopcreativekids.com/drawing/pastels/',
'https://www.shopcreativekids.com/wood-products/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/pens-pencils/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/velcro/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/crayons-color-pens-pencils/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/bags/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/markers-and-highlighters/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/labels/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/glue/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/note-pads/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/tape/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/notebooks/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/binders/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/scissors/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/tickets/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/index-cards/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/magnets/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/back-pack/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/calander/',
'https://www.shopcreativekids.com/back-to-school/school-and-office-supplies/calander/',
'https://www.shopcreativekids.com/sale/'
]

# file = open('out.txt', 'w', encoding='utf-8')
def get_all(url, id):
    try :
        global cur
        try:
            session = HTMLSession()
            src = session.get(url)
            soup = BeautifulSoup(src.html.raw_html, 'lxml')
        except Exception as e:
            print(e)
            return print('- Error in loading the page')
        try:
            pages = soup.find('div', class_ = 'pager row').find('div', class_ = 'left')
            pages = int(pages.text.split(' ')[-1])
        except: pages = 1
        # print(pages)
        # file.write(str(soup))
        # return
        page = 1
        while page <= pages:
            src = session.get(url + f'page{page}.html')
            soup = BeautifulSoup(src.html.raw_html, 'lxml')
            # file.write(str(soup))
            # return
            try:
                products = soup.find('div', class_ = 'col-sm-12 col-md-10').find_all('div', class_ = 'product col-xs-6 col-sm-3 col-md-3')
                for product in products:

                    try:
                        img = product.find('div').img['src']
                        # print(img)
                    except: img = ''

                    try:
                        link = product.find('div').a['href']
                        src = session.get(link)
                        soup = BeautifulSoup(src.html.raw_html, 'lxml')
                        # file.write(f"{str(link)}\n")
                    except: break

                    try:
                        price = soup.find("span", class_ = 'price').text.strip()
                        # print(price)
                    except:pass
                    
                    try:
                        info = soup.find('div', class_ = 'page info active').text.replace(" ", "").replace('\n', ' ').replace('   ', '\n').strip()
                        # print(info)
                    except:pass

                    try:
                        catgs = soup.find('div', class_ = 'col-sm-6 col-md-6 breadcrumbs text-right').text.replace(" ", "").replace('\n', '').strip()
                        catgs = ', '.join(catgs.split('/')[1:-1])
                        # print(catgs)
                    except:pass

                    try:
                        name = soup.find('h1', class_ = 'product-page').text.strip()
                        # print(name)
                    except:pass
                    # print('================\n')
                    data = [name, price, catgs, info, img, link]                    
    #             return
                    print(id, flush=True, end='.')
                    if cur == 0:
                        writing(data)
                    elif cur == 1:
                        writing1(data)
                    else:
                        writing2(data)
                    cur += 1
                    cur %= 3
                page += 1
            except Exception as e:
                # file.write(f"{link}\n")
                print("- Error in booksLinks")
                print(str(e))
        # print(f"\n[{id}] - {url}\n")
    except Exception as e:
        print(f"- Error in get_all - {url}")
        print(str(e))

row = 0
row1 = 0
row2 = 0
cur = 0

writer_lock = threading.Lock()
writer1_lock = threading.Lock()
writer2_lock = threading.Lock()

workbook = xlsxwriter.Workbook('1- shopcreativekids.com.xlsx')
worksheet = workbook.add_worksheet("data")
bold = workbook.add_format({'bold': True})

workbook1 = xlsxwriter.Workbook('1- shopcreativekids.com1.xlsx')
worksheet1 = workbook1.add_worksheet("data")

workbook2 = xlsxwriter.Workbook('1- shopcreativekids.com2.xlsx')
worksheet2 = workbook2.add_worksheet("data")

def writing(data):
    try:
        print('[0]', flush=True, end='.')
        with writer_lock:
            global row
            col = 0
            for key in (data):
                worksheet.write(row, col, key)
                col += 1
            row += 1
    except Exception as e:
        print("- Error in writing")
        print(str(e))

def writing1(data):
    try:
        print('[1]', flush=True, end='.')
        with writer1_lock:
            global row1
            col = 0
            for key in (data):
                worksheet1.write(row1, col, key)
                col += 1
            row1 += 1
    except Exception as e:
        print("- Error in writing1")
        print(str(e))

def writing2(data):
    try:
        print('[2]', flush=True, end='.')
        with writer2_lock:
            global row2
            col = 0
            for key in (data):
                worksheet2.write(row2, col, key)
                col += 1
            row2 += 1
    except Exception as e:
        print("- Error in writing2")
        print(str(e))

if __name__ == '__main__':
    try:
        data = ['Name', 'Price', 'Category', 'Information','Image_link', 'Link']
        col = 0
        for key in (data):
            worksheet.write(row, col, key, bold)
            col += 1
        row += 1
        with ThreadPoolExecutor(max_workers = 6) as executor:
            id = 0
            for url in urls:
                executor.submit(get_all, url, id)
                id += 1
                # break
        workbook.close()
        workbook1.close()
        workbook2.close()
        # file.close()
        print("FINISH :)")
    except Exception as e:
        print("- Error in main")
        print(str(e))