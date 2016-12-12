# coding: utf-8
from __future__ import print_function
import bs4
import sys
import urllib2
import urllib
import httplib
from socket import error as SocketError
import ssl
import os.path
import argparse
import multiprocessing as mp
#import threading as th
import datetime
from KindleReferencedIndexScoreClass import *
#from KindleReferencedIndexScoreDBs import *
#from KindleReferencedIndexScoreDBsSnapshotDealer import *
from KindleReferencedIndexScoreConfigMapper import *

SEED_EXIST          = True
SEED_NO_EXIST       = False
# set default state to scrape web pages in Amazon Kindle
def makeCookie(name, value):
    import cookielib
    return cookielib.Cookie(
        version=0, 
        name=name, 
        value=value,
        port=None, 
        port_specified=False,
        domain="kahdev.bur.st", 
        domain_specified=True, 
        domain_initial_dot=False,
        path="/", 
        path_specified=True,
        secure=False,
        expires=None,
        discard=False,
        comment=None,
        comment_url=None,
        rest=None
    )
import regex
def html_adhoc_fetcher(url):
    """ 
    標準のアクセス回数はRETRY_NUMで定義されている 
    """
    html = None
    retrys = [i for i in range(10)]
    for _ in retrys :
	import cookielib
	jar = cookielib.CookieJar()
	jar.set_cookie(makeCookie("session-token", CM.SESSION_TOKEN))
	jar.set_cookie(makeCookie("PHPSESSID", "375f0bb5f7425c4c75f3c7cd0123689a"))
	headers = {"Accept-Language": "en-US,en;q=0.5","User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0","Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Referer": "http://thewebsite.com","Connection": "keep-alive" } 
	request = urllib2.Request(url=url, headers=headers)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))
        _TIME_OUT = 5.
        try:
            html = opener.open(request, timeout = _TIME_OUT).read()
        except EOFError, e:
            print('[WARN] Cannot access url with EOFError, try number is...', e, _, url, mp.current_process() )
            continue
        except urllib2.URLError, e:
            print('[WARN] Cannot access url with URLError, try number is...', e, _, url, mp.current_process() )
            continue
        except urllib2.HTTPError, e:
            print('[WARN] Cannot access url with urllib2.httperror, try number is...', e, _, url, mp.current_process() )
            continue
        except ssl.SSLError, e:
            print('[WARN] Cannot access url with ssl error, try number is...', e, _, url, mp.current_process() )
            continue
        except httplib.BadStatusLine, e:
            print('[WARN] Cannot access url with BadStatusLine, try number is...', e, _, url, mp.current_process() )
            continue
        except httplib.IncompleteRead, e:
            print('[WARN] Cannot access url with IncompleteRead, try number is...', e, _, url, mp.current_process() )
            continue
        except SocketError, e:
            print('[WARN] Cannot access url with SocketError, try number is...', e, _, url, mp.current_process() )
            continue
        except UnicodeEncodeError, e:
            continue
        break
    if html == None:
        return (None, None, None)
    """
    remove extra data
    """
    line = html.replace('\n', '^A^B^C')
    line = regex.sub('<!--.*?-->', '',  line)
    line = regex.sub('<style.*?/style>', '',  line)
    html = regex.sub('<script.*?/script>', '', line ).replace('^A^B^C', '\n')
 
    soup = bs4.BeautifulSoup(html, "html.parser")
    title = (lambda x:unicode(x.string) if x != None else 'Untitled')(soup.title )
    return (html, title, soup)

linkbuffer = list()
def map_data_to_local_db_from_url(scraping_data, uniq_hash = ''):
    ScrapingDataHelp.attribute_valid(scraping_data)
    scraping_data.last_scrape_time = time.time()

    html, soup = None, None
    if scraping_data.html == None or scraping_data.html == "":
        scraping_data.html, title, soup = html_adhoc_fetcher(scraping_data.url)
        html                            = scraping_data.html
    else:
        html, soup = scraping_data.html, bs4.BeautifulSoup(scraping_data.html)
        pass
    if html == None or html == '' : return []
    """ 
    scraping_dataの子ノードをchild_soupsという変数名で返却
    """
    child_scraping_data_list = []
    for i, a in enumerate(set(map(lambda x:x['href'], soup.find_all('a', href=True) ) ) ):
        """ 
        アマゾン外のドメインの場合、全部パス 
        """
        if not 'www.amazon.co.jp' in a:
            continue
        """ 
        子ノードの作成 
        """
        child_scraping_data = ScrapingData()
        
        fixed_url = (lambda x: 'https://www.amazon.co.jp' + x if '/' == x[0] else x)(a)
        """ 
        '\n'コードを削除 ' 'を削除 
        """
        fixed_url = fixed_url.replace('\n','').replace(' ','')
        
        """ 
        ASINコードに類似していないURLは解析しない
        this data is too fresh, no need to scrape."""
        asin = get_asin(fixed_url)
        if not asin:
            continue
        
        if asin in linkbuffer:
            print('[INFO] This asin already in linkbuffer ', asin, len(linkbuffer) )
            continue
        else:
            if len(linkbuffer) < 1000:
               linkbuffer.append(asin)
            else:
               linkbuffer.pop(0)
        child_scraping_data.asin     = asin
        child_scraping_data.title    = 'Untitled'
        
        child_scraping_data.url     = fixed_url
        
        child_scraping_data.uniq_hash = uniq_hash

        child_scraping_data.normalized_url = '/'.join( filter( lambda x: not '=' in x, fixed_url.split('?').pop(0).split('/') ) )
                   
        
       	"""
	      SQLサーバにすでにqueryが存在していて古くないのならば、処理を行わない
	      """
        if SerializedUtils.is_too_old_query(child_scraping_data) == True:
          continue
        child_scraping_data.url = fixed_url
        child_scraping_data.last_scrape_time = time.time()

        """
        scraping_dataインスタンスが持つ、html情報を元に参照しているasinのコードをアップデート
        """
        scraping_data.asins.append(asin)

        """ 
        子ノードのhtml, titleを取得 
        """
        (child_scraping_data.html, child_scraping_data.title, soup ) = html_adhoc_fetcher(fixed_url)
        
        """ 
        データの取得かHTML解析に失敗していたらその行は抜かす 
        """
        if child_scraping_data.html == None or soup == None:
            continue
        child_scraping_data_list.append((child_scraping_data.normalized_url, child_scraping_data) )
        
        write_each(child_scraping_data)
    print('[DEBUG] Finish one loop, ', scraping_data.url, scraping_data.asins)
    write_each(scraping_data)
    return []

def evaluatate_other_page(normalized_url, scraping_data_list, from_url):
    split_url = normalized_url.split('?').pop(0) 
    obj_in_list = filter(lambda x:split_url in x[0], scraping_data_list)
    if obj_in_list == []:
        return
    obj = obj_in_list.pop()[1]
    normalized_from_url = from_url.split('?').pop(0).split('=').pop(0)
    #referenced_objs = filter(lambda x:x.from_url == normalized_from_url, obj.evaluated)
    if not normalized_from_url in set(map(lambda x:x.from_url, obj.evaluated)) :
        referenced_obj = Referenced() 
        referenced_obj.from_url = normalized_from_url
        obj.evaluated.append( referenced_obj )

def get_asin(url):
    asin = (lambda x:x.pop() if x != [] else '?')( filter(lambda x:len(x) == 10, url.split('?').pop(0).split('/')) )
    if asin[0] in ['A', 'B', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
        return asin
    return None

def validate_is_asin(scraping_data_list):
    #print scraping_data_list
    ret_list = []
    for url, scraping_data in scraping_data_list:
        is_asin = (lambda x:x.pop() if x != [] else '?')( filter(lambda x:len(x) == 10, url.split('?').pop(0).split('/')) )
        if is_asin[0] in ['A', 'B', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
            ret_list.append( (url, scraping_data) )
    return ret_list

def search_flatten_multiprocess(conn, chunked_list, all_scraping_data):
    to_increse_list = []
    for _, (url, scraping_data) in enumerate(chunked_list):
        if scraping_data.count >= 1:
            continue
        child_soups = map_data_to_local_db_from_url(scraping_data)
        for (url, child_soup) in child_soups:
            if is_already_query_exist(child_soup) == False:
                write_each(child_soup)
                print(child_soup.asin)
        
        scraping_data.count += 1
        print('[DEBUG] Eval ', scraping_data.asin, scraping_data.url, 'counter =', scraping_data.count, ' '.join( map(lambda x:str(x), [ _, '/', len(chunked_list), len(all_scraping_data), mp.current_process() ]) ) )

def search_flatten_multiprocess_with_leveldb(conn):
    db = plyvel.DB('./' + SnapshotDeal.DIST_LDB_NAME, create_if_missing=True)
    for k,v in db:
      scraping_data = pickle.loads(v.replace('', '\n'))
      map_data_to_local_db_from_url(scraping_data)
      print('[DEBUG] Eval ', scraping_data.asin, scraping_data.url, 'counter =', scraping_data.count, ' '.join( map(lambda x:str(x), [ _, '/', mp.current_process() ]) ) )

def search_flatten_multiprocess_with_sql(conn, uniq_hash, index):
    for results in get_all_data_iter_box():
      """
      自分のプロセスナンバーだけ、取り出す
      """
      keyurl, scraping_data = results[index]
      if hasattr(scraping_data, 'uniq_hash') and scraping_data.uniq_hash != uniq_hash:
        scraping_data.uniq_hash = uniq_hash
        map_data_to_local_db_from_url(scraping_data, uniq_hash)
        print('[DEBUG] Eval ', scraping_data.asin, scraping_data.url, 'counter =', scraping_data.count, ' '.join( map(lambda x:str(x), [ _, '/', mp.current_process() ]) ) )
      elif not hasattr(scraping_data, 'uniq_hash'):
        setattr(scraping_data, 'uniq_hash', uniq_hash)
        map_data_to_local_db_from_url(scraping_data, uniq_hash)
        print('[DEBUG] Eval ', scraping_data.asin, scraping_data.url, 'counter =', scraping_data.count, ' '.join( map(lambda x:str(x), [ _, '/', mp.current_process() ]) ) )

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i+n]

import signal
def exit_gracefully(signum, frame):
    # restore the original signal handler as otherwise evil things will happen
    # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
    signal.signal(signal.SIGINT, original_sigint)
    try:
        if raw_input("\nReally quit? (y/n)> ").lower().startswith('y'):
            sys.exit(1)
    except KeyboardInterrupt:
        print("Ok ok, quitting")
        sys.exit(1)
    signal.signal(signal.SIGINT, exit_gracefully)

import plyvel
import cPickle as pickle
import re
import json
def url_stack_control( records ):
    pass
    return set()

if __name__ == '__main__':
    # store the original SIGINT handler
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, exit_gracefully)

    parser = argparse.ArgumentParser(description='Process Kindle Referenced Index Score.')
    parser.add_argument('--URL', help='set default URL which to scrape at first')
    parser.add_argument('--depth', help='how number of url this program will scrape')
    parser.add_argument('--mode', help='you can specify mode...')
    parser.add_argument('--refresh', help='create snapshot(true|false)')
    parser.add_argument('--file', help='input filespath')

    args_obj = vars(parser.parse_args())
  
    depth = (lambda x:int(x) if x else 10)( args_obj.get('depth') )
    
    mode = (lambda x:x if x else 'undefined')( args_obj.get('mode') )

    refresh    = (lambda x:False if x=='false' else True)( args_obj.get('refresh') )

    filename = args_obj.get('file')

    if mode == 'local' or mode == 'level':
      db = plyvel.DB('./tmp/pixiv_htmls', create_if_missing=True)
      """
      SnapshotDealデーモンが出力するデータをもとにスクレイピングを行う
      NOTE: SQLの全アクセスは非常に動作コストが高く、推奨されない
      NOTE: Snapshotが何もない場合、initialize_parse_and_map_data_to_local_dbを呼び出して初期化を行う
      """
      
      links = set(["http://www.pixiv.net/search.php?word=%E8%89%A6%E3%81%93%E3%82%8C&order=date_d&p=29"])

      if db.get('___URLS___') != None:
        for link in json.loads(db.get('___URLS___')):
          links.add(link)
        print("リカバリーしました")

      while links != set() :
        url = links.pop()
        #print('url', url)
        def analyzing(links):
          for _ in range(100):
            html, title, soup = html_adhoc_fetcher(url)
            if soup == None: 
              #print('コンテンツが空でした', url)
              continue
            else:
              break
          if soup == None:
            print('まじむりっす、ごめんなさい', url)
            return

          tags = soup.find_all('a' )
          tags_save = []
          for tag in tags:
              urllocal = tag.get('href')
              if urllocal != None and '/tags.php?tag=' in urllocal:
                urlparam = urllocal.split('=').pop()
                decode_urlparam = urllib.unquote(urlparam.encode('utf-8'))
                tags_save.append(decode_urlparam)
          
          def parse_img(url):
            import urllib, random
            import cookielib
            jar = cookielib.CookieJar()
            jar.set_cookie(makeCookie("PHPSESSID", "5994399_b2be5341b1a9b7c34088e962b697a261"))
            ses_rand = int(randam.random()*2 )
            jar.set_cookie(makeCookie("device_token", "08a49c60aaeb60e12623e7ba23b31e22"))
            headers = {"Accept-Language": "en-US,en;q=0.5","User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0","Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Referer": "http://thewebsite.com","Connection": "keep-alive"  } 
            request = urllib2.Request(url=imgurl, headers=headers)
            request.add_header('Referer', url)
            opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))

            linker = str(random.random()) + "," + str(random.random())
            for _ in range(1000):
              n = 1024*1024
              try:
                con = opener.open(request).read(n)
                if len(con) == 0:
                    print("ゼロエラーです", url)
                    continue
                file('./tmp/' + linker + '.jpg', 'w').write(con)
                break
              except:
                continue
            db.put(str(url), json.dumps({'linker':linker + '.jpg', 'tags': tags_save }) )
            print("発見した画像", ' '.join(tags_save), url, imgurl)

          for imgurl in filter(lambda x:x!=None, [img.get('src') for img in  soup.find_all('img')]):
                  #if '艦これ' not in tags_save and '艦隊これくしょん' not in tags_save:
                  #    print('目的以外の画像です', ' '.join(tags_save))
                  #    break
            if '600x600' not in str(imgurl):
              continue
            import threading as T
            t = T.Thread(target=parse_img, args=(url,))
            t.start()
          if db.get(str(url)) == None and 'member_illust.php?' in url:
              db.put(str(url), 'miss')
          
          tags = soup.find_all('a' )
          for tag in tags:
              urllocal = tag.get('href')
              try:
                  str(urllocal)
              except:
                  continue
              if urllocal != None and '/tags.php?tag=' in urllocal:
                continue
                #fullurl = 'http://www.pixiv.net/' + urllocal
                #if db.get(str(fullurl)) == None:
                #    links.add(fullurl)
                #    db.put(str(fullurl), 'dummy')
              if urllocal != None and '/search.php?word=' in urllocal:
                fullurl = 'http://www.pixiv.net/' + urllocal
                if '%E8%89%A6%E3%81%93%E3%82%8C' in fullurl and db.get(str(fullurl)) == None and 'novel' not in fullurl:
                    urlparam = urllocal.split('=').pop()
                    decode_urlparam = urllib.unquote(urlparam.encode('utf-8'))
                    links.add(fullurl)
                    db.put(str(fullurl), 'dummy')
              if urllocal != None and '/member_illust.php?' in urllocal:
                if 'http://' not in urllocal:
                    fullurl = 'http://www.pixiv.net/' + urllocal
                else:
                    fullurl = urllocal
                if db.get(str(fullurl)) == None and 'novel' not in fullurl:
                    links.add(fullurl)
          db.put('___URLS___', json.dumps(list(links)))
          print("残りURLは", len(links), "です")
        import threading as T
        t = T.Thread(target=analyzing, args=(links,))
        t.start()
        #print("theadの数は" , T.active_count())
        while T.active_count() > 50:
            import time 
            time.sleep(0.12)
        #analyzing(links)




if mode == 'leveldump' or mode == 'localdump':
        db = plyvel.DB('./tmp/pixiv_htmls', create_if_missing=True)
        for k, raw in db:
            if k == '___URLS___': continue
            try:
                json.loads(raw)
            except:
                continue
            for k, v in json.loads(raw).items():
                if isinstance(v, list):
                    print(' '.join(map(lambda x:x.encode('utf-8'), set(v))), end=" ")
                else:
                    print(v, end=" ")
            print()


import MeCab
import math
import json
if mode ==  'makeidf' :
    idf = {}
    c = 0
    for line in open(filename).read().split('\n'):
        c += 1
        line = line.strip()
        if line == '' : continue
        tp  = line.lower().split(' ')
        head = tp.pop(0)
        contents = ''.join(tp)
        m = MeCab.Tagger ("-Owakati")
        for t in set(m.parse(contents).strip().split(' ')):
            if idf.get(t) == None:
                idf[t] = 1
            else:
                idf[t] += 1

    it = {}
    ti = {}
    for i, (t, n) in enumerate(sorted(idf.items(), key=lambda x:x[1]*-1)):
        idf[t] = math.log( float(c)/n )
        ti[t] = i
        it[i] = t
  
    open(filename + '.idf.json', 'w').write(json.dumps(idf))
    open(filename + '.it.json', 'w').write(json.dumps(it))
    open(filename + '.ti.json', 'w').write(json.dumps(ti))
    for t, w in sorted(idf.items(), key=lambda x:x[1]*-1):
        print(t, w)

        
if mode ==  'makesvm' :
    idf = json.loads(open(filename + '.idf.json').read())
    it  = json.loads(open(filename + '.it.json').read())
    ti  = json.loads(open(filename + '.ti.json').read())
    import random
    from collections import Counter
    inputs = list(filter(lambda x:x != '', open(filename).read().split('\n')))
    random.shuffle(inputs)
    for line in inputs:
        line = line.strip()
        if line == '' : continue
        tp  = line.lower().split(' ')
        head = int(float(tp.pop(0)))
        contents = ''.join(tp)
        m = MeCab.Tagger ("-Owakati")
        res = []
        if head in [1, 2, 3]:
            print(0, end=" ")
        elif head in [5]:
            print(1, end=" ")
        else: 
            continue

        for t, num in Counter(m.parse(contents).strip().split(' ')).items():
            t = t.decode('utf-8')
            res.append([ti[t], num*idf[t]])
        for e, l in enumerate(sorted(res, key=lambda x:x[0])):
            if e == 0: continue
            print(':'.join(map(str, l)), end=" ")
        print()

if mode == "dumplinear":
    it  = json.loads(open(filename + '.it.json').read())
    evals = filter(lambda x:x!='', open(filename + '.model').read().split('\n'))
    tw = {}
    fixer = 0
    for i, e in enumerate(evals[6:]):
        tw[it.get(str(i+1)).encode('utf-8')] = float(e) 
    for t, w in sorted(tw.items(), key=lambda x:x[1]*-1):
        print(t,w)

if mode == 'score':
    tsv = filter(lambda x:x != '', open('stash/star_ranking.tsv').read().split('\n'))
    trank = {}
    for t_w in tsv:
        t, w = t_w.split(' ')
        trank[t] = float(w)
    import json
    import math
    idf = json.loads(open(filename + '.idf.json').read())
    m = MeCab.Tagger ("-Owakati")
    for line in sys.stdin:
        score = 0.
        line = line.strip()
        for t in m.parse(line).strip().split(' '):
            if idf.get(t.decode('utf-8')) != None and trank.get(t) != None:
                score += idf.get(t.decode('utf-8')) * trank.get(t)
        res = int(1. / (1. + math.pow(math.e, score*-1 ) ) * 100)
        if res < 50.:
            print("だめっぽい文章", end=" ")
        else:
            print("よいっぽい文章", end=" ")
        print("score =", res)