import scrapy
import pandas as pd
import logging
import json
import requests
from scrapy.http import Request
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import random
import time

class AmazonSponsoredProductSpider(scrapy.Spider):
    name = 'amazon_sponsored_spider'
    
    def __init__(self, keywords=None, asins=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keywords = keywords or []
        self.asins = asins or []
        self.ua = UserAgent()
        self.scrape_do_token = 'f34af83da83344aaaef4610472245c8cbed7ec8abf4'

    def start_requests(self):
        for keyword, asin in zip(self.keywords, self.asins):
            url = f"https://www.amazon.in/s?k={keyword.replace(' ', '+')}"
            yield Request(
                url=self.get_scrape_do_url(url), 
                callback=lambda response, keyword=keyword, asin=asin: self.parse_sponsored_products(response, keyword, asin),
                meta={
                    'keyword': keyword,
                    'asin': asin,
                    'dont_retry': True,
                    'handle_httpstatus_all': True
                }
            )

    def get_scrape_do_url(self, url):
        """Generate Scrape.do URL with token"""
        return f"https://api.scrape.do?token={self.scrape_do_token}&url={url}"

    def parse_sponsored_products(self, response, keyword, asin):
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            sponsored_products = self.find_sponsored_products(soup)
            
            if not sponsored_products:
                yield {
                    'Keyword': keyword,
                    'ASIN': asin,
                    'Sponsored Placement': 'Not Found'
                }
                return

            for sponsored_position, product in enumerate(sponsored_products, 1):
                product_asin = self.extract_asin(product)
                
                if product_asin == asin:
                    yield {
                        'Keyword': keyword,
                        'ASIN': asin,
                        'Sponsored Placement': sponsored_position
                    }
                    return

            # If ASIN not found in sponsored products
            yield {
                'Keyword': keyword,
                'ASIN': asin,
                'Sponsored Placement': 'Not Found'
            }

        except Exception as e:
            self.logger.error(f"Error parsing sponsored products: {e}")
            yield {
                'Keyword': keyword,
                'ASIN': asin,
                'Sponsored Placement': 'Error'
            }

    def find_sponsored_products(self, soup):
        """Find sponsored products using multiple selectors"""
        sponsored_products = []
        
        # Method 1: SP Sponsored Results
        sp_sponsored = soup.find_all('div', attrs={"data-component-type": "sp-sponsored-result"})
        sponsored_products.extend(sp_sponsored)
        
        # Method 2: AdHolder class
        ad_holders = soup.find_all('div', class_="s-result-item AdHolder")
        sponsored_products.extend([ad for ad in ad_holders if ad not in sponsored_products])
        
        # Method 3: Sponsored Label
        search_results = soup.find_all('div', attrs={"data-component-type": "s-search-result"})
        for result in search_results:
            sponsored_label = result.find('span', string=lambda text: text and 'Sponsored' in text)
            if sponsored_label and result not in sponsored_products:
                sponsored_products.append(result)
        
        return sponsored_products

    def extract_asin(self, product):
        """Extract ASIN from product element"""
        methods = [
            lambda p: p.get('data-asin'),
            lambda p: p.find('div', attrs={"data-asin": True}).get('data-asin') if p.find('div', attrs={"data-asin": True}) else None,
            lambda p: p.find(attrs={"data-asin": True}).get('data-asin') if p.find(attrs={"data-asin": True}) else None
        ]

        for method in methods:
            asin = method(product)
            if asin:
                return asin
        return None

def run_spider(keywords, asins):
    """Helper function to run spider and return results"""
    from scrapy.crawler import CrawlerProcess
    from scrapy.settings import Settings
    
    results = []
    
    def collect_item(item):
        results.append(item)
    
    crawler_settings = Settings()
    crawler_settings.set('FEEDS', {})
    crawler_settings.set('USER_AGENT', UserAgent().random)
    crawler_settings.set('LOG_ENABLED', False)
    
    process = CrawlerProcess(settings=crawler_settings)
    
    process.crawl(AmazonSponsoredProductSpider, 
                  keywords=keywords, 
                  asins=asins,
                  )
    
    process.start()
    
    return results
