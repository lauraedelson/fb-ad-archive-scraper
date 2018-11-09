import sys
import random
import psycopg2
import psycopg2.extras
from time import sleep
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from io import BytesIO
from collections import deque
from urllib.parse import urlencode
from urllib3.util import Timeout
from datetime import datetime
import os
import csv
import json
import requests
from collections import OrderedDict
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import configparser
from bs4 import BeautifulSoup

csv.field_size_limit(sys.maxsize)

if len(sys.argv) < 2:
    exit("Usage:python3 page_scraper.py page_scraper.cfg")

def find_ad_class(driver):
    divs = deque([driver.find_element_by_id('content')])
    while divs:
        div = divs.popleft()
        if '1px solid rgb(233, 234, 235)' == div.value_of_css_property('border'):
            return div.get_attribute('class')
        divs.extend(div.find_elements_by_xpath('div'))
    return None


def find_topnav_div(driver):
    divs = deque([driver.find_element_by_id('content')])
    while divs:
        div = divs.popleft()
        if 'fixed' == div.value_of_css_property('position'):
            return div
        divs.extend(div.find_elements_by_xpath('div'))
    return None


def class_to_css_selector(clazz):
    # This handles compound class names.
    return ".{}".format(clazz.replace(' ', '.'))


def main(text, ad_ids, ad_limit=None, headless=True):
    timestamp = datetime.now()
    q = text
        
    options = webdriver.ChromeOptions()
    options.add_argument('--proxy-server=socks5://localhost:9050')
    if headless:
        options.add_argument('headless')

    caps = DesiredCapabilities.CHROME
    caps['loggingPrefs'] = {'performance': 'ALL'}

    driver = webdriver.Chrome(options=options, desired_capabilities=caps)
    driver.implicitly_wait(10)
    try:
        print(q)
        driver.get('https://www.facebookcorewwwi.onion/ads/archive/?{}'.format(urlencode({'active_status': 'all', 'q': q, 'ad_type':'political_and_issue_ads'})))
        sleep(5)
        # Has results
        try:
            driver.find_element_by_xpath('//div[contains(text(),"There are no ads matching")]')
            print('No results')
            
        except NoSuchElementException:
            pass

        print('got results')
        jar = requests.cookies.RequestsCookieJar()
        for cookie in driver.get_cookies():
            jar.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])

        ads_performance_logs = []
        ads_creative_logs = []
        for entry in driver.get_log('performance'):
            msg = json.loads(entry['message'])
            if msg.get('message', {}).get('method', {}) == 'Network.requestWillBeSent':
                url = msg['message']['params']['request']['url']
                if url.startswith('https://www.facebookcorewwwi.onion/ads/archive/async/search_ads'):
                    ads_creative_logs.append(msg)

        
        tmp_results = {}
        # Ads creative
        for page, msg in enumerate(ads_creative_logs):

            tor_proxy = dict(http='socks5h://localhost:9050',
                             https='socks5h://localhost:9050')

            try:
                r = requests.post(msg['message']['params']['request']['url'],
                                  headers=msg['message']['params']['request']['headers'],
                                  data=msg['message']['params']['request']['postData'],
                                  cookies=jar, proxies=tor_proxy)
                r.raise_for_status()
            except  requests.exceptions.ConnectionError:
                print("Connection error")
                return
            except requests.exceptions.HTTPError:
                print("Page is down")
                return

            payload = json.loads(r.text[9:])
            if not payload or not payload['payload'] or not payload['payload']['results']:
                break

            #print(payload)
            for result in payload['payload']['results']:
                curr_ad_id = result['adid']
                if curr_ad_id in ad_ids:
                    print("Found our ad!")
                    tmp_results[curr_ad_id] = result['adArchiveID']


        results = {}
        for ad_id in ad_ids:
            if ad_id in tmp_results:
                results[ad_id] = tmp_results[ad_id]

        return results

    finally:
        driver.close()
        driver.quit()

    print('Done')


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(sys.argv[1])

    existing_ads = set()
    with open('mapped_ads.txt') as old_ads:
        for row in old_ads:
            parts = row.split(",")
            existing_ads.add(parts[0])

    with open('ads_to_check.txt') as other_old_ads:
        for row in other_old_ads:
            existing_ads.add(row.strip())

    print(len(existing_ads))
    #search arguments
    ads = {}
    with open(config['SEARCH']['TERMS']) as search_term_file:
        csv_reader = csv.DictReader(search_term_file)
        header = csv_reader
        for row in csv_reader:
            markup = row['message']
            soup = BeautifulSoup(markup)
            date_str = row['created_at']
            parts = date_str.split(' ')
            created_date = datetime.strptime(parts[0], '%Y-%m-%d').date()
            archive_start_date = datetime.strptime('2018-05-01', '%Y-%m-%d').date()
            if created_date >= archive_start_date and row['id'] not in existing_ads:
                body = soup.get_text()
                if body in ads:
                    ads[body].append(row['id'])
                else:
                    ads[body] = [row['id']]

    headless = config['SEARCH']['HEADLESS'] == 'True'
    depth = config['SEARCH']['DEPTH']
    print(len(ads))

    try:
        ad_output = open('ads_to_check.txt', 'a')
        mapped_output = open('mapped_ads.txt', 'a')
        for text, ad_ids in ads.items():
            mappings = main(text, ad_ids, int(depth), headless)
            if mappings:
                for ad_id, archive_id in mappings.items():
                    if archive_id:
                        mapped_output.write(ad_id + ',' + archive_id + '\n')
                    else:
                        ad_output.write(ad_id + '\n')

    finally:
        ad_output.close()
        mapped_output.close()
