#!/usr/bin/env python3
"""
2025 Global News Scraper (Restored)
Target: All news available from 2025 on energy/AI/blockchain topics with full article content
Destination: DynamoDB (newsroom_articles table)
Strict adherence to docs/INGESTION_CONTRACT.md.
"""

import os
import re
import json
import time
import logging
import requests
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# Setup paths for Zorora environment
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.research.article_tagger import tag_article  # noqa: E402
from tools.research.newsroom_dynamodb import insert_article  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("news_scraper")

# Set fresh mode flag
FRESH_MODE = os.environ.get('FRESH_MODE', 'false').lower() == 'true'

if not os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    parser = argparse.ArgumentParser(description='News Collection Script (DynamoDB)')
    parser.add_argument('-fresh', '--fresh', action='store_true', 
                       help='Run in fresh mode - bypass idempotency and reprocess all articles')
    args, _ = parser.parse_known_args()
    FRESH_MODE = args.fresh

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------

# Track progress - use /tmp in Lambda environment
PROGRESS_FILE = "/tmp/news_scraper_progress.json" if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') else "news_scraper_progress.json"

# Search keywords - comprehensive energy, AI, blockchain, and finance terms
NEWS_KEYWORDS = [
    # Core topics
    "energy", "electricity", "blockchain", "artificial intelligence", "AI", "insurance",
    
    # Energy technologies
    "renewable energy", "solar power", "wind energy", "battery storage",
    "smart grid", "microgrid", "electric vehicles", "capacity market",
    "demand response", "carbon pricing", "carbon tax", "feed-in tariff",
    "grid reliability", "transmission planning", "levelized cost of energy", 
    "power purchase agreement", "green bond", "ESG investment", "coal", "rare earth minerals", "lithium", "nuclear",
    "gas","oil","supply chain",

    # Insurance/Risk
    "catastrophe modeling", "exposure data", "reinsurance", "underwriting", 
    "climate risk", "war","civil unrest","protest","climate risk",
    
    # Technology
    "cybersecurity", "digital twin", "predictive analytics",
    
    # Major agencies and regulatory bodies
    "Federal Energy Regulatory Commission", "FERC",
    "North American Electric Reliability Corporation", "NERC",
    "Department of Energy", "DOE",
    "Environmental Protection Agency", "EPA",
    "National Renewable Energy Laboratory", "NREL",
    "International Energy Agency", "IEA",
    "Commodity Futures Trading Commission", "CFTC",
    "Insurance Regulatory and Development Authority", "IRDAI",
    "Standard & Poor's", "Moody's", "Fitch",
    "Bloomberg"
]

# News sources - Full 100+ source inventory
NEWS_SOURCES = {
    'rss_feeds': [
        # BBC News
        'https://feeds.bbci.co.uk/news/rss.xml',
        'https://feeds.bbci.co.uk/news/world/rss.xml',
        'https://feeds.bbci.co.uk/news/business/rss.xml',
        'https://feeds.bbci.co.uk/news/technology/rss.xml',
        'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml',
        
        # CNN
        'http://rss.cnn.com/rss/cnn_topstories.rss',
        'http://rss.cnn.com/rss/edition.rss',
        'http://rss.cnn.com/rss/cnn_world.rss',
        
        # Guardian
        'https://www.theguardian.com/world/rss',
        'https://www.theguardian.com/business/rss',
        'https://www.theguardian.com/technology/rss',
        'https://www.theguardian.com/environment/rss',
        
        # Al Jazeera
        'https://www.aljazeera.com/xml/rss/all.xml',
        
        # Financial/Business
        'https://www.marketwatch.com/rss/topstories',
        'https://feeds.finance.yahoo.com/rss/2.0/headline',
        
        # Tech/Industry
        'https://feeds.arstechnica.com/arstechnica/index',
        'https://techcrunch.com/feed/',
        'https://www.wired.com/feed/rss',
        'https://feeds.feedburner.com/venturebeat/SZYF',
        
        # Academic/Research
        'https://rss.arxiv.org/rss/econ',
        'https://rss.arxiv.org/rss/cs.AI',
        'https://rss.arxiv.org/rss/cs.CL',
        
        # Energy/Policy focused
        'https://www.energy.gov/rss/all.xml',
        'https://www.whitehouse.gov/feed/',
        
        # International
        'https://feeds.cfr.org/feeds/site/current.xml',
        
        # Energy Industry Publications
        'https://feeds.feedburner.com/EnergyCentral',
        'https://feeds.feedburner.com/TDWorld',
        'https://www.powermag.com/feed/',
        'https://www.tdworld.com/rss.xml',
        'https://feeds.feedburner.com/RenewableEnergyWorld',
        'https://www.renewableenergyworld.com/rss/',
        'https://www.cleanenergywire.org/rss.xml',
        'https://feeds.feedburner.com/GreentechMedia',
        'https://www.worldoil.com/rss/',
        
        # Energy Technology & Storage
        'https://feeds.feedburner.com/SmartGridNews',
        'https://feeds.feedburner.com/EnergyStorageNews',
        'https://feeds.feedburner.com/NuclearEnergyInstitute',
        'https://feeds.feedburner.com/WorldNuclearNews',
        
        # Supply Chain & Materials
        'https://feeds.feedburner.com/CriticalMaterials',
        'https://www.mining.com/rss/',
        
        # International Energy Organizations
        'https://feeds.feedburner.com/IEA',
        'https://www.irena.org/rss/',
        
        # Regional Energy Sources
        'https://feeds.feedburner.com/EnergyPost',
        'https://www.canadianenergy.com/rss/',
        
        # Energy News & Analysis
        'https://feeds.feedburner.com/EnergyInDepth',
        'https://feeds.feedburner.com/EnergyWire',
        'https://feeds.feedburner.com/GlobalEnergy',
        'https://feeds.feedburner.com/WorldEnergy',
        'https://feeds.feedburner.com/EnergyTransition',
        'https://feeds.feedburner.com/AfricaIntelligence',
        'https://feeds.feedburner.com/IntelligenceOnline',

        # Intelligence & Security Analysis
        'https://feeds.feedburner.com/Stratfor',
        'https://feeds.feedburner.com/CSIS',
        'https://feeds.feedburner.com/CFR',
        'https://feeds.feedburner.com/AtlanticCouncil',
        'https://feeds.feedburner.com/DefenseNews',
        'https://feeds.feedburner.com/DefenseOne',
        'https://feeds.feedburner.com/WarOnTheRocks',
        'https://feeds.feedburner.com/JustSecurity',
        'https://feeds.feedburner.com/Lawfare',
        'https://feeds.feedburner.com/ForeignAffairs',
        'https://feeds.feedburner.com/ForeignPolicy',

        # US Legislation - Congress.gov
        'https://www.congress.gov/rss/introduced-in-house.xml',
        'https://www.congress.gov/rss/introduced-in-senate.xml',
        'https://www.congress.gov/rss/passed-house.xml',
        'https://www.congress.gov/rss/passed-senate.xml',
        'https://www.congress.gov/rss/became-law.xml',
        'https://www.congress.gov/rss/todays-house-floor.xml',
        'https://www.congress.gov/rss/todays-senate-floor.xml',
        'https://www.congress.gov/rss/committee-schedule.xml',
        'https://www.congress.gov/rss/house-committee-meetings.xml',
        'https://www.congress.gov/rss/senate-committee-meetings.xml',
        'https://www.congress.gov/rss/most-viewed-bills.xml',

        # Legislation - International
        'https://bills.parliament.uk/RSS/AllBills.rss',
        'https://eur-lex.europa.eu/rss/en/oj_latest.xml',
        'https://www.aph.gov.au/rss/housebills',
        'https://www.aph.gov.au/rss/senatebills',
        'https://www.camara.leg.br/noticias/rss/todas-as-noticias.xml',
        'https://www12.senado.leg.br/noticias/rss',
        'https://pmg.org.za/rss/',

        # AFRICA
        'https://www.premiumtimesng.com/rss',
        'https://www.thisdaylive.com/rss',
        'https://guardian.ng/rss',
        'https://businessday.ng/rss',
        'https://www.citizen.co.za/rss',
        'https://dailynewsegypt.com/rss',
        'https://www.egyptindependent.com/rss',
        'https://www.moroccoworldnews.com/rss',
        'https://www.myjoyonline.com/rss',
        'https://dailynews.co.tz/rss',
        'https://observer.ug/rss',
        'https://www.independent.co.ug/rss',
        'https://www.namibian.com.na/rss',
        'https://www.gabonreview.com/rss',
        'https://expressodasilhas.cv/rss',

        # LATIN AMERICA
        'https://www.infomoney.com.br/rss',
        'https://www.excelsior.com.mx/rss',
        'https://www.elfinanciero.com.mx/rss',
        'https://www.latercera.com/rss',
        'https://www.larepublica.co/rss',
        'https://peru21.pe/rss',
        'https://www.eltiempo.com.ve/rss',
        'https://www.elcomercio.com/rss',
        'https://www.elpais.com.uy/rss',
        'https://www.stabroeknews.com/rss',
        'https://www.kaieteurnewsonline.com/rss',
        'https://www.guyanachronicle.com/rss',

        # MENA
        'https://www.aljazeera.com/rss',
        'https://www.tehrantimes.com/rss',
        'https://www.middleeastmonitor.com/feed/',
        'https://www.middleeasteye.net/rss',
        'https://www.newarab.com/rss',
        'https://www.al-monitor.com/rss',
        'https://themedialine.org/rss',
        'https://www.lemauricien.com/rss',
        'https://www.lanation.dj/rss',
        'https://www.dabangasudan.org/rss',
        'https://eyeradio.org/rss',
        'https://www.newsroom.gy/rss',
        'https://dailynewsegypt.com/rss',
        'https://www.egyptindependent.com/rss',
        'https://www.moroccoworldnews.com/rss'
    ],
    'direct_scraping': [
        'https://www.reuters.com/technology/',
        'https://www.reuters.com/business/energy/',
        'https://techcrunch.com/',
        'https://www.theverge.com/',
        'https://arstechnica.com/',
        'https://www.wired.com/',
        'https://www.coindesk.com/',
        'https://cointelegraph.com/'
    ]
}

# -------------------------------------------------------------------------
# PROGRESS TRACKING
# -------------------------------------------------------------------------
class ProgressTracker:
    def __init__(self, progress_file=PROGRESS_FILE):
        self.progress_file = progress_file
        self.progress = self.load_progress()
    
    def load_progress(self):
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            "rss_feeds": {"feeds_completed": []},
            "direct_scraping": {"sources_completed": []},
            "total_articles": 0,
            "last_updated": None
        }
    
    def save_progress(self):
        self.progress["last_updated"] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def mark_feed_complete(self, feed_url):
        if feed_url not in self.progress["rss_feeds"]["feeds_completed"]:
            self.progress["rss_feeds"]["feeds_completed"].append(feed_url)
            self.save_progress()
    
    def is_feed_complete(self, feed_url):
        if FRESH_MODE:
            return False
        return feed_url in self.progress["rss_feeds"].get("feeds_completed", [])
    
    def mark_source_complete(self, source_url):
        if source_url not in self.progress["direct_scraping"]["sources_completed"]:
            self.progress["direct_scraping"]["sources_completed"].append(source_url)
            self.save_progress()
    
    def is_source_complete(self, source_url):
        if FRESH_MODE:
            return False
        return source_url in self.progress["direct_scraping"].get("sources_completed", [])
    
    def increment_articles(self, count=1):
        self.progress["total_articles"] += count
        self.save_progress()

progress_tracker = ProgressTracker()

# -------------------------------------------------------------------------
# EXTRACTION UTILITIES
# -------------------------------------------------------------------------
def extract_full_article_content(url: str) -> Optional[str]:
    """Extract full article content from URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'ads']):
            element.decompose()
        
        content_selectors = [
            'article', '[data-module="ArticleBody"]', '.article-body', '.story-body',
            '.post-content', '.entry-content', '.content', 'main', '.article-content'
        ]
        
        article_content = None
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                article_content = content_element.get_text(separator='\n', strip=True)
                if len(article_content) > 200:
                    break
        
        if not article_content:
            paragraphs = soup.find_all('p')
            article_content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        return article_content if len(article_content) > 100 else None
    except Exception as e:
        logger.debug(f"Extraction failed for {url}: {e}")
        return None

def matches_keywords(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    for keyword in NEWS_KEYWORDS:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, text_lower):
            return True
    return False

def is_2025_article(date_str: str) -> bool:
    if not date_str:
        return True
    year_match = re.search(r'202[5-9]', date_str)
    return True if year_match else ('2025' in date_str)

# -------------------------------------------------------------------------
# COLLECTION LOGIC
# -------------------------------------------------------------------------
def process_single_rss_feed(feed_url: str):
    if progress_tracker.is_feed_complete(feed_url):
        return 0
        
    logger.info(f"Processing RSS feed: {feed_url}")
    feed_count = 0
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(feed_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item') or soup.find_all('entry')
        
        for item in items:
            try:
                title = item.find('title').get_text() if item.find('title') else 'No Title'
                
                link_elem = item.find('link')
                link = link_elem.get('href') if link_elem and link_elem.get('href') else (link_elem.get_text() if link_elem else None)
                
                description = item.find('description').get_text() if item.find('description') else ''
                
                if not link or not matches_keywords(title + ' ' + description):
                    continue
                
                pub_date_elem = (item.find('pubDate') or item.find('published') or item.find('updated'))
                pub_date = pub_date_elem.get_text() if pub_date_elem else ''
                
                if not is_2025_article(pub_date):
                    continue
                
                full_content = extract_full_article_content(link)
                if not full_content:
                    continue
                
                tags = tag_article(title + ' ' + full_content, NEWS_KEYWORDS)
                
                # Special tagging for legislation
                special_tags = []
                legislation_domains = ['congress.gov', 'parliament.uk', 'eur-lex.europa.eu', 'aph.gov.au', 'camara.leg.br', 'senado.leg.br', 'pmg.org.za']
                if any(dom in feed_url for dom in legislation_domains):
                    special_tags.append('legislation')
                
                metadata = {
                    'url': link,
                    'title': title,
                    'source': 'RSS Feed',
                    'pub_date': pub_date,
                    'description': description,
                    'feed_url': feed_url,
                    'full_content': full_content,
                    'collection_date': datetime.now().isoformat(),
                    'tags': {**tags, 'special_tags': special_tags}
                }
                
                if insert_article(metadata):
                    feed_count += 1
                    progress_tracker.increment_articles()
                
                time.sleep(0.2)
            except Exception as e:
                logger.debug(f"Item error: {e}")
                continue
        
        progress_tracker.mark_feed_complete(feed_url)
        return feed_count
    except Exception as e:
        logger.error(f"Feed error {feed_url}: {e}")
        return 0

def process_rss_feeds():
    feeds = [f for f in NEWS_SOURCES['rss_feeds'] if not progress_tracker.is_feed_complete(f)]
    if not feeds:
        return
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(process_single_rss_feed, feeds))

def scrape_website(base_url: str):
    if progress_tracker.is_source_complete(base_url):
        return 0
    logger.info(f"Scraping website: {base_url}")
    found = 0
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(base_url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')

        links = {urljoin(base_url, a['href']) for a in soup.find_all('a', href=True) 
                 if any(p in a['href'] for p in ['/article/', '/news/', '/story/', '/post/'])}

        for url in list(links)[:25]:
            try:
                full_content = extract_full_article_content(url)
                if not full_content or not matches_keywords(full_content):
                    continue

                tags = tag_article(full_content, NEWS_KEYWORDS)
                metadata = {
                    'url': url,
                    'title': urlparse(url).path.split('/')[-1].replace('-', ' ').title(),
                    'source': 'Direct Scraping',
                    'pub_date': datetime.now().isoformat(), # Direct scraping often lacks clear date
                    'full_content': full_content,
                    'collection_date': datetime.now().isoformat(),
                    'tags': tags
                }

                if insert_article(metadata):
                    found += 1
                    progress_tracker.increment_articles()
            except Exception:
                continue

        progress_tracker.mark_source_complete(base_url)
        return found

    except Exception as e:
        logger.error(f"Scrape error {base_url}: {e}")
        return 0

def process_direct_scraping():
    for source in NEWS_SOURCES['direct_scraping']:
        scrape_website(source)
        time.sleep(2)

def main():
    logger.info("Starting Global News Collection (DynamoDB)")
    start_time = time.time()
    try:
        process_rss_feeds()
        process_direct_scraping()
    except Exception as e:
        logger.error(f"Fatal: {e}")
    finally:
        logger.info(f"Complete. Total: {progress_tracker.progress['total_articles']} articles. Time: {(time.time()-start_time)/60:.1f}m")

if __name__ == "__main__":
    main()
