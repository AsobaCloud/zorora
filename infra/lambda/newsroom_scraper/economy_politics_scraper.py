#!/usr/bin/env python3
"""
Economy & Politics Scraper
Restored and aligned with docs/INGESTION_CONTRACT.md.
"""

import os
import re
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
from tools.research.article_tagger import detect_continents, detect_countries  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("economy_politics_scraper")

# Set fresh mode flag
FRESH_MODE = os.environ.get('FRESH_MODE', 'false').lower() == 'true'

# Track progress
PROGRESS_FILE = "/tmp/economy_politics_scraper_progress.json" if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') else "economy_politics_scraper_progress.json"

class ProgressTracker:
    def __init__(self, progress_file=PROGRESS_FILE):
        self.progress_file = progress_file
        self.progress = self.load_progress()
    def load_progress(self):
        if os.path.exists(self.progress_file):
            import json
            return json.load(open(self.progress_file))
        return {"rss_feeds": {"feeds_completed": []}, "total_articles": 0}
    def save_progress(self):
        self.progress["last_updated"] = datetime.now().isoformat()
        import json
        json.dump(self.progress, open(self.progress_file, 'w'), indent=2)
    def mark_feed_complete(self, feed_url):
        if feed_url not in self.progress["rss_feeds"]["feeds_completed"]:
            self.progress["rss_feeds"]["feeds_completed"].append(feed_url)
            self.save_progress()
    def is_feed_complete(self, feed_url):
        return False if FRESH_MODE else feed_url in self.progress["rss_feeds"].get("feeds_completed", [])

progress_tracker = ProgressTracker()

ECONOMIC_KEYWORDS = ["consumer spending", "retail sales", "inflation", "CPI", "GDP", "economic growth", "interest rate", "monetary policy", "fiscal policy"]
POLITICAL_KEYWORDS = ["election", "voter", "polling", "political party", "parliament", "congress", "prime minister", "president", "sanctions"]
ALL_KEYWORDS = ECONOMIC_KEYWORDS + POLITICAL_KEYWORDS

FEEDS_BY_COUNTRY = {
    "Zimbabwe": ["https://www.zimlive.com/feed/", "https://www.zimlive.com/category/business/feed/"],
    "India": ["https://www.livemint.com/rss/economy", "https://www.livemint.com/rss/politics"],
    "China": ["https://www.caixinglobal.com/rss.html", "https://merics.org/en/rss.xml"],
    "Brazil": ["https://braziljournal.com/feed/", "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml"],
    "USA": ["https://thehill.com/feed/", "https://www.politico.com/rss/politicopicks.xml", "https://api.axios.com/feed/"],
    "Eurozone": ["https://www.politico.eu/feed/", "https://euobserver.com/rss.xml"],
    "South Africa": ["https://www.dailymaverick.co.za/feed/", "https://feeds.24.com/articles/news24/TopStories/rss"],
    "Nigeria": ["https://punchng.com/feed/", "https://www.thisdaylive.com/feed/"],
    "Kenya": ["https://www.standardmedia.co.ke/rss/headlines.php"],
    "Ghana": ["https://www.myjoyonline.com/feed/"],
    "Mauritius": ["https://defimedia.info/feed"],
    "DR Congo": ["https://www.radiookapi.net/feed"]
}

def extract_full_article_content(url: str) -> Optional[str]:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(["script", "style"]):
            s.decompose()
        content = soup.select_one('article') or soup.select_one('.article-content') or soup.select_one('body')
        return content.get_text(separator='\n', strip=True) if content else None
    except Exception:
        return None

def process_single_economy_politics_feed(feed_url: str, target_country: str):
    if progress_tracker.is_feed_complete(feed_url):
        return 0
    logger.info(f"Processing economy/politics feed ({target_country}): {feed_url}")
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
                
                combined_text = title + ' ' + (item.find('description').get_text() if item.find('description') else '') + ' ' + full_content
                if not any(re.search(r'\b' + re.escape(k.lower()) + r'\b', combined_text.lower()) for k in ALL_KEYWORDS):
                    continue
                
                metadata = {
                    'url': link,
                    'title': title,
                    'source': 'Economy/Politics Feed',
                    'pub_date': (item.find('pubDate') or item.find('published')).get_text() if (item.find('pubDate') or item.find('published')) else datetime.now().isoformat(),
                    'full_content': full_content,
                    'collection_date': datetime.now().isoformat(),
                    'tags': {
                        'continents': detect_continents(combined_text),
                        'countries': detect_countries(combined_text),
                        'special_tags': ['economy_politics'],
                        'target_country': target_country
                    }
                }
                if insert_article(metadata):
                    count += 1
                    progress_tracker.progress['total_articles'] += 1
            except Exception:
                continue
        progress_tracker.mark_feed_complete(feed_url)
        return count
    except Exception:
        return 0

def process_economy_politics_feeds():
    feeds = []
    for country, urls in FEEDS_BY_COUNTRY.items():
        for url in urls:
            feeds.append((url, country))
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(lambda x: process_single_economy_politics_feed(*x), feeds))

if __name__ == "__main__":
    process_economy_politics_feeds()
