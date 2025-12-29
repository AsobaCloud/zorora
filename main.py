"""Entry point for Claude Code-like REPL."""

import sys
import os
import logging
from repl import REPL
from config import LOGGING_LEVEL, LOGGING_FORMAT, LOG_FILE

# Configure logging
# Always write to file
handlers = [logging.FileHandler(LOG_FILE)]

# Only add console handler if --verbose flag is set
if '--verbose' in sys.argv or '-v' in sys.argv:
    # Use stderr for logs (not stdout) to keep stdout clean for user output
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    handlers.append(console_handler)

logging.basicConfig(
    level=LOGGING_LEVEL,
    format=LOGGING_FORMAT,
    handlers=handlers
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
    
    # Register ONA platform commands (if configured)
    try:
        from zorora.commands.ona_platform import register_ona_commands
        register_ona_commands(repl)
    except ImportError:
        # ONA commands not available (optional feature)
        pass
    except Exception as e:
        logger.warning(f"Failed to register ONA commands: {e}")
    
    try:
        repl.run()
    finally:
        # Ensure terminal is restored even if there's an error
        repl.ui.cleanup()
    
    # Clean up logging handlers before exit
    logging.shutdown()
    
    # Explicit clean exit (use sys.exit to allow proper cleanup)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
