#!/usr/bin/python
# thanks to https://mlvnt.com/blog/tech/2018/05/scraping-deviantart/

from bs4 import BeautifulSoup
from selenium import webdriver
from queue import Queue
from threading import Thread, Lock
import requests, time, sys, pathlib, os, re

def get_urls():
    print('loading image urls....', end=''); sys.stdout.flush()
    options = webdriver.FirefoxOptions()
    options.add_argument('--headless')
    options.add_argument('--safe-mode')
    fox = webdriver.Firefox(options=options)
    #fox.get('https://www.deviantart.com/' + sys.argv[1] + '/favourites/')
    fox.get('https://www.deviantart.com/' + sys.argv[1] + '/gallery/?catpath=/')
    time.sleep(4)
    last_height = fox.execute_script("return document.body.scrollHeight")
    links = []
    while True:
        fox.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        t = fox.find_elements_by_class_name('torpedo-thumb-link')
        for i in t: links.append(i.get_attribute('href'))
        new_height = fox.execute_script("return document.body.scrollHeight")
        if new_height == last_height: break
        last_height = new_height
    fox.close()
    print('done')
    return list(set(links))

def save_image(l, lock):
    try:
        s = requests.Session()
        h = {'User-Agent': 'Firefox'}
        soup = BeautifulSoup(s.get(l, headers=h).text, 'html.parser')
        name = soup.find('title').text.lower().replace(' ','_').replace('_on_deviantart','').replace('/','')
        name += '_' + l.split('/')[-1].split('-')[-1]

        if pathlib.Path(os.path.join(sys.argv[2],name)+'.png').is_file(): return
        if pathlib.Path(os.path.join(sys.argv[2],name)+'.jpg').is_file(): return
        if pathlib.Path(os.path.join(sys.argv[2],name)+'.gif').is_file(): return

        try: link = soup.find('a', class_='dev-page-download')['href']
        except:
            try: link = soup.find('img', class_='dev-content-full')['src']
            except: # mature content
                options = webdriver.FirefoxOptions()
                options.add_argument('--headless')
                options.add_argument('--safe-mode')
                fox = webdriver.Firefox(options=options)
                fox.get(l)
                time.sleep(1)
                fox.find_element_by_class_name('datefields')
                fox.find_elements_by_class_name('datefield')
                fox.find_element_by_id('month').send_keys('01')
                fox.find_element_by_id('day').send_keys('01')
                fox.find_element_by_id('year').send_keys('1991')
                fox.find_element_by_class_name('tos-label').click()
                fox.find_element_by_class_name('submitbutton').click()
                time.sleep(6)
                try: link = fox.find_element_by_class_name('dev-page-download').get_attribute('href')
                except: link = fox.find_element_by_class_name('dev-content-full').get_attribute('src')
                h['Cookie']=''
                for i in fox.get_cookies(): h['Cookie']+=i['name']+'='+i['value']+'; '
                fox.close()
        req = s.get(link, headers=h)
        ext = re.findall('.+/(.+)',req.headers['Content-Type'])[0]
        if ext=='html': print(l, 'failed'); return
        if ext=='jpeg': ext='jpg'
        name += '.' + ext
        with open(os.path.join(sys.argv[2], name),'wb') as file: file.write(req.content)
        with lock: global img_count; img_count+=1
        print(str(img_count), '-', name, 'saved')
    except: print(l, 'failed')

def worker_thread(q, lock):
    while True:
        link = q.get()
        if link is None or link=='':
            q.task_done(); break
        save_image(link, lock)
        q.task_done()

if __name__ == "__main__":
    if len(sys.argv)==2: sys.argv.append('.')
    if len(sys.argv)!=3: print('Usage', sys.argv[0], 'username [path]'); exit(0)
    
    workers = 40
    img_count = 0
    threads = []
    q = Queue()
    lock = Lock()
    start = time.time()
    
    pathlib.Path(sys.argv[2]).mkdir(parents=True, exist_ok=True)
    
    if pathlib.Path(os.path.join(sys.argv[2],'links.txt')).is_file():
        links = open(os.path.join(sys.argv[2],'links.txt'),'r').read().split('\n')
    else:
        links = get_urls()
        with open(os.path.join(sys.argv[2],'links.txt'), 'w') as f:
            for i in links: f.write(i+'\n')

    if input(str(len(links))+' images found, download all? (y/n) ')=='y': 
        for i in links: q.put(i)

    for i in range(workers):
         t = Thread(target=worker_thread, args=(q, lock))
         t.start()
         threads.append(t)
    
    for _ in range(workers): q.put(None)
    q.join()
    for t in threads: t.join() 

    end = time.time()
    print(); print(len(links), 'images found')
    print(img_count, 'images saved')
    print('elapsed time:', int(end-start), 'sec')
