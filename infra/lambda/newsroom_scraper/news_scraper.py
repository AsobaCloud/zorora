#!/usr/bin/env python3
"""
2025 News Scraper with DynamoDB Storage
Target: All news available from 2025 on energy/AI/blockchain topics with full article content
Destination: DynamoDB (newsroom_articles table)
Features: URL-based idempotency via conditional writes, full content with S3 overflow for large articles
"""

import os
import json
import time
import logging
import requests
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# Setup path before other imports
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.research.article_tagger import tag_article
from tools.research.newsroom_dynamodb import insert_article

# Track progress - use /tmp in Lambda environment
PROGRESS_FILE = "/tmp/news_scraper_progress.json" if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') else "news_scraper_progress.json"

# Search keywords - comprehensive energy, AI, blockchain, and finance terms
NEWS_KEYWORDS = [
    # Core topics
    "energy", "electricity", "blockchain", "artificial intelligence", "AI", "insurance",
    # Energy infrastructure
    "grid", "transmission", "distribution", "power plant", "renewable", "solar", "wind",
    "nuclear", "hydro", "geothermal", "biomass", "battery", "storage", "smart grid",
    # Energy markets
    "electricity market", "power market", "energy trading", "wholesale", "retail", "tariff",
    "regulation", "deregulation", "utility", "independent system operator", "ISO", "RTO",
    # Blockchain and crypto
    "bitcoin", "ethereum", "cryptocurrency", "crypto", "blockchain", "decentralized",
    "smart contract", "defi", "nft", "mining", "proof of work", "proof of stake",
    # AI and technology
    "machine learning", "deep learning", "neural network", "GPT", "LLM", "generative AI",
    "automation", "robotics", "computer vision", "natural language processing",
    # Finance and investment
    "investment", "funding", "venture capital", "private equity", "IPO", "stock market",
    "commodity", "trading", "hedge fund", "asset management", "ESG", "sustainable finance",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("news_scraper")

# Set fresh mode flag
FRESH_MODE = os.environ.get('FRESH_MODE', 'false').lower() == 'true'

if not os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    parser = argparse.ArgumentParser(description='News Collection Script with DynamoDB Storage')
    parser.add_argument('-fresh', '--fresh', action='store_true',
                       help='Run in fresh mode - bypass idempotency and reprocess all articles')
    args, _ = parser.parse_known_args()
    FRESH_MODE = args.fresh


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

    def increment_articles(self, count=1):
        self.progress["total_articles"] += count
        self.save_progress()


progress_tracker = ProgressTracker()


# RSS Feeds to scrape
RSS_FEEDS = [
    # Energy & Power
    "https://www.eia.gov/rss-files/press_releases.xml",
    "https://www.eia.gov/rss-files/todayinenergy.xml",
    "https://www.reuters.com/rssFeed/businessNews",
    "https://www.reuters.com/rssFeed/energy",
    "https://www.reuters.com/rssFeed/technologyNews",
    
    # AI & Tech
    "https://www.artificialintelligence-news.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    
    # Blockchain & Crypto
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
]


def extract_full_article_content(url: str) -> Optional[str]:
    """Extract full article content from URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try common content selectors
        content_selectors = [
            'article',
            '[role="article"]',
            '.article-content',
            '.post-content',
            '.entry-content',
            'main',
        ]
        
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                # Remove script/style elements
                for script in content(['script', 'style', 'nav', 'footer', 'header']):
                    script.decompose()
                return content.get_text(separator='\n', strip=True)
        
        return None
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {e}")
        return None


def process_rss_feed(feed_url: str):
    """Process a single RSS feed and ingest articles to DynamoDB."""
    if progress_tracker.is_feed_complete(feed_url) and not FRESH_MODE:
        logger.info(f"Skipping completed feed: {feed_url}")
        return
    
    logger.info(f"Processing RSS feed: {feed_url}")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(feed_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch feed {feed_url}: {response.status_code}")
            return
        
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        if not items:
            items = soup.find_all('entry')  # Atom feeds
        
        processed_count = 0
        
        for item in items:
            try:
                # Extract article data
                title = item.find('title')
                title = title.get_text() if title else "Untitled"
                
                link = item.find('link')
                if link:
                    url = link.get_text() if hasattr(link, 'get_text') else link.get('href', '')
                else:
                    guid = item.find('guid')
                    url = guid.get_text() if guid else ""
                
                if not url:
                    continue
                
                pub_date = item.find('pubDate')
                pub_date = pub_date.get_text() if pub_date else ""
                
                description = item.find('description')
                description = description.get_text() if description else ""
                
                # Extract full content
                full_content = extract_full_article_content(url)
                if not full_content:
                    full_content = description
                
                # Tag the article
                keywords = NEWS_KEYWORDS
                tags = tag_article(full_content, keywords)
                
                # Build metadata for DynamoDB
                metadata = {
                    'url': url,
                    'title': title,
                    'source': urlparse(url).netloc,
                    'pub_date': pub_date,
                    'description': description,
                    'full_content': full_content,
                    'tags': tags,
                    'feed_url': feed_url,
                }
                
                # Insert to DynamoDB (idempotent via conditional write)
                if insert_article(metadata):
                    processed_count += 1
                    progress_tracker.increment_articles()
                
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                continue
        
        logger.info(f"Processed {processed_count} articles from {feed_url}")
        progress_tracker.mark_feed_complete(feed_url)
        
    except Exception as e:
        logger.error(f"Error processing feed {feed_url}: {e}")


def process_rss_feeds():
    """Process all RSS feeds."""
    logger.info("Starting RSS feed processing...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_rss_feed, RSS_FEEDS)
    
    logger.info(f"RSS feed processing complete. Total articles: {progress_tracker.progress['total_articles']}")


def main():
    """Main entry point."""
    logger.info("Starting 2025 News Collection (DynamoDB-backed)")
    logger.info(f"Fresh mode: {FRESH_MODE}")
    
    start_time = time.time()
    
    try:
        # Process RSS feeds
        process_rss_feeds()
        
    except KeyboardInterrupt:
        logger.info("Collection interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        elapsed = time.time() - start_time
        logger.info(f"News collection complete. Total time: {elapsed/60:.1f} minutes")
        logger.info(f"Total articles collected: {progress_tracker.progress['total_articles']}")


if __name__ == "__main__":
    main()
