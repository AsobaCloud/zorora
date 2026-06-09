from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Add current directory and repo root to path for imports
MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import the restored scraper modules
import news_scraper  # noqa: E402
import polymarket_scraper  # noqa: E402
import legislation_scraper  # noqa: E402
import economy_politics_scraper  # noqa: E402

def lambda_handler(event, context):
    """
    Lambda entry point for newsroom scraper suite.
    Strictly follows docs/INGESTION_CONTRACT.md.
    """
    try:
        os.environ.setdefault("DYNAMODB_TABLE_NAME", "newsroom_articles")
        os.environ.setdefault("AWS_REGION", "us-east-1")
        
        # Determine mode from event
        mode = event.get('mode', 'news') if event else 'news'
        fresh_mode = event.get('fresh_mode', False) if event else False
        
        if fresh_mode:
            os.environ['FRESH_MODE'] = 'true'
            news_scraper.FRESH_MODE = True
            polymarket_scraper.FRESH_MODE = True
            legislation_scraper.FRESH_MODE = True
            economy_politics_scraper.FRESH_MODE = True

        results = {}
        
        if mode == 'news' or mode == 'all':
            print("Running Global News Scraper...")
            news_scraper.main()
            results['news'] = news_scraper.progress_tracker.progress['total_articles']
            
        if mode == 'polymarket' or mode == 'all':
            print("Running Polymarket Scraper...")
            polymarket_scraper.process_polymarket_feeds()
            results['polymarket'] = polymarket_scraper.progress_tracker.progress['total_articles']
            
        if mode == 'legislation' or mode == 'all':
            print("Running Legislation Scraper...")
            legislation_scraper.process_legislation_feeds()
            results['legislation'] = legislation_scraper.progress_tracker.progress['total_articles']
            
        if mode == 'economy' or mode == 'all':
            print("Running Economy/Politics Scraper...")
            economy_politics_scraper.process_economy_politics_feeds()
            results['economy'] = economy_politics_scraper.progress_tracker.progress['total_articles']

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Collection suite complete (mode: {mode})",
                "results": results,
                "timestamp": datetime.now().isoformat()
            }),
        }
    except Exception as e:
        print(f"Error in scraper Lambda: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat()
            }),
        }
