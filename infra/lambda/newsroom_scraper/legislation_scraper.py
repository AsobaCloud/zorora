#!/usr/bin/env python3
"""
Legislation Scraper - Collects ALL articles from legislative sources
Restored and aligned with docs/INGESTION_CONTRACT.md.
"""

import os
import json
import logging
import requests
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# Setup paths for Zorora environment
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.research.newsroom_dynamodb import insert_article  # noqa: E402
from tools.research.article_tagger import detect_continents  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("legislation_scraper")

# Set fresh mode flag
FRESH_MODE = os.environ.get('FRESH_MODE', 'false').lower() == 'true'

# Track progress
PROGRESS_FILE = "/tmp/legislation_scraper_progress.json" if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') else "legislation_scraper_progress.json"

class ProgressTracker:
    def __init__(self, progress_file=PROGRESS_FILE):
        self.progress_file = progress_file
        self.progress = self.load_progress()
    
    def load_progress(self):
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {"rss_feeds": {"feeds_completed": []}, "total_articles": 0}
    
    def save_progress(self):
        self.progress["last_updated"] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def mark_feed_complete(self, feed_url):
        if feed_url not in self.progress["rss_feeds"]["feeds_completed"]:
            self.progress["rss_feeds"]["feeds_completed"].append(feed_url)
            self.save_progress()
    
    def is_feed_complete(self, feed_url):
        return False if FRESH_MODE else feed_url in self.progress["rss_feeds"].get("feeds_completed", [])

progress_tracker = ProgressTracker()

LEGISLATION_RSS_FEEDS = [
    'https://www.govinfo.gov/rss/bills.xml',
    'https://www.rollcall.com/feed/',
    'https://www.senate.gov/rss/press-releases.xml',
    'https://mg.co.za/politics/feed/',
    'https://bills.parliament.uk/RSS/AllBills.rss',
    'https://eur-lex.europa.eu/rss/en/oj_latest.xml',
    'https://www.aph.gov.au/rss/housebills',
    'https://www.aph.gov.au/rss/senatebills',
    'https://www.camara.leg.br/noticias/rss/todas-as-noticias.xml',
    'https://www12.senado.leg.br/noticias/rss',
    'https://pmg.org.za/rss/'
]

def extract_full_article_content(url: str) -> Optional[str]:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(["script", "style"]):
            s.decompose()
        
        content = soup.select_one('article') or soup.select_one('.article-content') or soup.select_one('main') or soup.select_one('body')
        if content:
            return content.get_text(separator='\n', strip=True)
        return None
    except Exception:
        return None

def process_single_legislation_feed(feed_url: str):
    if progress_tracker.is_feed_complete(feed_url):
        return 0
    logger.info(f"Processing legislation RSS feed: {feed_url}")
    count = 0
    try:
        response = requests.get(feed_url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item') or soup.find_all('entry')
        
        for item in items:
            try:
                title = item.find('title').get_text() if item.find('title') else 'No Title'
                link_elem = item.find('link')
                link = link_elem.get('href') if link_elem and link_elem.get('href') else (link_elem.get_text() if link_elem else None)
                if not link:
                    continue
                
                full_content = extract_full_article_content(link)
                if not full_content:
                    continue
                
                metadata = {
                    'url': link,
                    'title': title,
                    'source': 'Legislation Feed',
                    'pub_date': (item.find('pubDate') or item.find('published') or item.find('updated')).get_text() if (item.find('pubDate') or item.find('published')) else datetime.now().isoformat(),
                    'description': item.find('description').get_text() if item.find('description') else '',
                    'full_content': full_content,
                    'collection_date': datetime.now().isoformat(),
                    'tags': {
                        'continents': detect_continents(title + ' ' + full_content),
                        'special_tags': ['legislation']
                    }
                }
                
                if insert_article(metadata):
                    count += 1
                    progress_tracker.progress['total_articles'] += 1
            except Exception:
                continue
        progress_tracker.mark_feed_complete(feed_url)
        return count
    except Exception as e:
        logger.error(f"Error {feed_url}: {e}")
        return 0

def process_legislation_feeds():
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(process_single_legislation_feed, LEGISLATION_RSS_FEEDS))

if __name__ == "__main__":
    process_legislation_feeds()
