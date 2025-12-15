"""Entry point for Claude Code-like REPL."""

import sys
import logging
from repl import REPL
from config import LOGGING_LEVEL, LOGGING_FORMAT, LOG_FILE

# Configure logging
logging.basicConfig(
    level=LOGGING_LEVEL,
    format=LOGGING_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Initialize and run REPL."""
    # Test LM Studio connection
    print("Testing LM Studio connection...")
    try:
        import requests
        test_response = requests.get("http://localhost:1234/v1/models", timeout=5)
        test_response.raise_for_status()
        print("✓ LM Studio is running\n")
    except Exception as e:
        print(f"⚠ Warning: Could not connect to LM Studio: {e}")
        print("  Make sure LM Studio is running on http://localhost:1234\n")

    # Initialize and run REPL
    repl = REPL()
    repl.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
