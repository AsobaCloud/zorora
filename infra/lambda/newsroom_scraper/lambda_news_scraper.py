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

        results = {}
        
        if mode == 'news' or mode == 'all':
            import news_scraper
            if fresh_mode:
                news_scraper.FRESH_MODE = True
            print("Running Global News Scraper...")
            news_scraper.main()
            if hasattr(news_scraper, 'progress_tracker'):
                results['news'] = news_scraper.progress_tracker.progress['total_articles']
            else:
                results['news'] = 0
            
        if mode == 'polymarket' or mode == 'all':
            import polymarket_scraper
            if fresh_mode:
                polymarket_scraper.FRESH_MODE = True
            print("Running Polymarket Scraper...")
            polymarket_scraper.process_polymarket_feeds()
            if hasattr(polymarket_scraper, 'progress_tracker'):
                results['polymarket'] = polymarket_scraper.progress_tracker.progress['total_articles']
            else:
                results['polymarket'] = 0
            
        if mode == 'legislation' or mode == 'all':
            import legislation_scraper
            if fresh_mode:
                legislation_scraper.FRESH_MODE = True
            print("Running Legislation Scraper...")
            legislation_scraper.process_legislation_feeds()
            if hasattr(legislation_scraper, 'progress_tracker'):
                results['legislation'] = legislation_scraper.progress_tracker.progress['total_articles']
            else:
                results['legislation'] = 0
            
        if mode == 'economy' or mode == 'all':
            import economy_politics_scraper
            if fresh_mode:
                economy_politics_scraper.FRESH_MODE = True
            print("Running Economy/Politics Scraper...")
            economy_politics_scraper.process_economy_politics_feeds()
            if hasattr(economy_politics_scraper, 'progress_tracker'):
                results['economy'] = economy_politics_scraper.progress_tracker.progress['total_articles']
            else:
                results['economy'] = 0

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
