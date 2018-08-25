#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tester....
"""
from __future__ import print_function
import re
import sys
import time
import argparse
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

SESSION = requests.Session()
SESSION.mount('http://', HTTPAdapter(max_retries=5))
SESSION.mount('https://', HTTPAdapter(max_retries=5))

SLEEP_TIMEOUT = 10

def eprint(*args, **kwargs):
    """ print data in std error """
    print(*args, file=sys.stderr, **kwargs)

def get_urls(parser):
    """ returns all url parsed on the given regions """
    valid_colors = ['#cccc66', '#ded9ac', 'khaki']
    td_filter = {'width': '70', 'bgcolor': valid_colors}
    region = "europe"
    urls = []
    eprint('Getting %s region...' % region)
    url = 'http://www.lyngsat.com/' + region + '.html'
    res = SESSION.get(url)
    #eprint(res.text.encode('utf-8'))
    page = BeautifulSoup(res.text, parser)
    for tds in page.find_all('td', td_filter):
        urls.append(tds.find('a')['href'])
    time.sleep(SLEEP_TIMEOUT)
    return urls

res = SESSION.get('https://httpbin.org/headers')
eprint(res.text)

time_created = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
urls = time_created + '\n\nLXML:\n' + '\n'.join(get_urls('lxml')) + '\n\nhtml.parser:\n' + '\n'.join(get_urls('html.parser'))
eprint(urls)
open("satellites.xml", "w").write(urls)
