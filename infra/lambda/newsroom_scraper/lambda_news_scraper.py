from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

# Add repo root for tools imports
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def lambda_handler(event, context):
    try:
        os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
        os.environ.setdefault("FRESH_MODE", "false")
        os.environ.setdefault("DYNAMODB_TABLE_NAME", "newsroom_articles")
        
        from news_scraper import main

        main()
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "News scraper completed successfully",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": f"Error running news scraper: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        }
