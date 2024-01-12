import requests
from bs4 import BeautifulSoup

def login(username, password):
    session = requests.Session()
    submission_page = session.get(f"https://codeforces.com/enter").content
    soup = BeautifulSoup(submission_page, 'html.parser')
    form_data = {}
    form_data['csrf_token'] = soup.find('input', {'name': 'csrf_token'}).get('value')
    login_data = {
        'csrf_token': form_data['csrf_token'],
        'action': 'enter',
        'handleOrEmail': username,
        'password': password,
        'remember': 'on',
    }
    session.post('https://codeforces.com/enter', data = login_data)
    session.post('https://www.google.com')
    response = session.get('https://codeforces.com')
    soup = BeautifulSoup(response.content, 'html.parser')
    print(soup.find('div', {'id': 'header'}).findAll('a')[-2].text)

if __name__ == "__main__":
    login('Kareem_Khaled', '1389928kk')

