#!/usr/bin/env python3
"""
Polymarket Scraper - Collects political prediction markets
Restored and aligned with docs/INGESTION_CONTRACT.md.
"""

import re
import logging
import requests
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Setup paths for Zorora environment
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.research.newsroom_dynamodb import insert_article  # noqa: E402
from tools.research.article_tagger import detect_continents  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("polymarket_scraper")

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------

POLYMARKET_API_URL = "https://gamma-api.polymarket.com/markets"
POLYMARKET_WEB_BASE = "https://polymarket.com/event"

# Political/geopolitical keywords for filtering markets
POLITICAL_KEYWORDS = [
    "election", "president", "presidential", "congress", "senate",
    "governor", "parliament", "prime minister", "vote", "voter",
    "republican", "democrat", "conservative", "liberal",
    "trump", "biden", "desantis", "harris", "pence", "newsom",
    "war", "conflict", "invasion", "military", "nato", "sanctions",
    "tariff", "trade war", "treaty", "diplomacy", "nuclear",
    "legislation", "bill", "law", "policy", "regulation",
    "impeachment", "supreme court", "federal reserve", "fed rate",
    "putin", "zelensky", "xi jinping", "netanyahu", "eu ", "european union"
]

# Country detection patterns (subset of article_tagger logic for market-specific filtering)
COUNTRY_PATTERNS = {
    "United States": [r"\bUS\b", r"\bUSA\b", r"United States", r"America"],
    "United Kingdom": [r"\bUK\b", r"United Kingdom", r"Britain"],
    "China": [r"China", r"Chinese"],
    "Russia": [r"Russia", r"Russian", r"Putin"],
    "Ukraine": [r"Ukraine", r"Ukrainian", r"Zelensky"],
    "Israel": [r"Israel", r"Israeli", r"Netanyahu"],
    "Iran": [r"Iran", r"Iranian"],
    "South Africa": [r"South Africa", r"South African"],
    "Nigeria": [r"Nigeria", r"Nigerian"],
    "Brazil": [r"Brazil", r"Brazilian"]
}

def detect_countries(text: str) -> List[str]:
    countries = []
    for country, patterns in COUNTRY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                countries.append(country)
                break
    return sorted(countries)

def is_political_market(market: Dict) -> bool:
    category = (market.get("category") or "").lower()
    if any(kw in category for kw in ["politics", "election", "government", "current-affairs"]):
        return True
    combined = (market.get("question") or "").lower() + " " + (market.get("description") or "").lower()
    return any(re.search(r'\b' + re.escape(kw.lower()) + r'\b', combined) for kw in POLITICAL_KEYWORDS)

def fetch_markets(limit: int = 100, offset: int = 0) -> List[Dict]:
    try:
        params = {"limit": limit, "offset": offset, "closed": "false", "order": "volume", "ascending": "false"}
        response = requests.get(POLYMARKET_API_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching Polymarket: {e}")
        return []

def market_to_article_content(market: Dict) -> str:
    question = market.get("question", "Unknown Market")
    description = market.get("description", "")
    outcomes = market.get("outcomes", [])
    prices = market.get("outcomePrices", [])
    
    price_display = []
    for i, outcome in enumerate(outcomes):
        if i < len(prices):
            try:
                price_display.append(f"{outcome}: {float(prices[i]) * 100:.1f}%")
            except Exception:
                pass

    return f"<h1>{question}</h1><p>{description}</p><h3>Current Prices</h3><ul>" + "".join(f"<li>{p}</li>" for p in price_display) + "</ul>"

def process_polymarket_feeds() -> int:
    logger.info("=== POLYMARKET SCRAPER: Starting ===")
    all_markets = []
    for offset in [0, 100, 200]:
        markets = fetch_markets(limit=100, offset=offset)
        if not markets:
            break
        all_markets.extend([m for m in markets if is_political_market(m)])

    
    saved_count = 0
    for market in all_markets:
        try:
            question = market.get("question", "Unknown Market")
            slug = market.get("slug", market.get("id", ""))
            url = f"{POLYMARKET_WEB_BASE}/{slug}"
            combined_text = f"{question} {market.get('description', '')}"
            
            metadata = {
                'url': url,
                'title': question,
                'source': 'Polymarket',
                'pub_date': market.get("startDate") or datetime.now().isoformat(),
                'description': market.get("description", "")[:500],
                'full_content': market_to_article_content(market),
                'collection_date': datetime.now().isoformat(),
                'tags': {
                    'continents': detect_continents(combined_text),
                    'countries': detect_countries(combined_text),
                    'core_topics': ['geopolitics'],
                    'special_tags': ['prediction_market']
                }
            }
            
            if insert_article(metadata):
                saved_count += 1
                logger.info(f"Saved market: {question[:50]}...")
        except Exception as e:
            logger.error(f"Error processing market: {e}")
            continue
    return saved_count

if __name__ == "__main__":
    process_polymarket_feeds()
