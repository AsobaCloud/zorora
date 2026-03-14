"""Entry point for Claude Code-like REPL."""

import sys
import os
import logging
import threading
import time
from repl import REPL
from config import LOGGING_LEVEL, LOGGING_FORMAT, LOG_FILE
import config
from workflows.market_workflow import MarketWorkflow
from workflows.regulatory_workflow import RegulatoryWorkflow
from tools.alerts.store import AlertStore
from workflows.alert_runner import execute_alert

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


def _start_market_refresh_thread():
    """Start a daemon thread that incrementally updates stale market series."""
    def _refresh_loop():
        while True:
            try:
                wf = MarketWorkflow()
                updated = wf.update_all()
                if updated:
                    logger.info("Background refresh: updated %d series", updated)
            except Exception as e:
                logger.debug("Background refresh failed: %s", e)
            time.sleep(config.MARKET_DATA.get("stale_threshold_hours", 24) * 3600)

    t = threading.Thread(target=_refresh_loop, daemon=True, name="market-refresh")
    t.start()
    return t


def _start_regulatory_refresh_thread():
    """Start a daemon thread that incrementally updates stale regulatory sources."""
    def _refresh_loop():
        while True:
            try:
                workflow = RegulatoryWorkflow()
                updated = workflow.update_all()
                if updated:
                    logger.info("Background regulatory refresh: updated %d sources", updated)
            except Exception as e:
                logger.debug("Background regulatory refresh failed: %s", e)
            time.sleep(config.REGULATORY.get("stale_threshold_hours", 168) * 3600)

    t = threading.Thread(target=_refresh_loop, daemon=True, name="regulatory-refresh")
    t.start()
    return t


def _start_alert_check_thread():
    """Start a daemon thread that executes due digest alerts."""
    def _alert_loop():
        while True:
            try:
                store = AlertStore()
                due = store.get_due_alerts()
                for alert in due:
                    execute_alert(alert, store)
            except Exception as e:
                logger.debug("Alert check failed: %s", e)
            time.sleep(config.ALERTS.get("check_interval_seconds", 300))

    t = threading.Thread(target=_alert_loop, daemon=True, name="alert-check")
    t.start()
    return t


def main():
    """Initialize and run REPL."""
    endpoint_key = config.MODEL_ENDPOINTS.get("orchestrator", "local")
    print(f"Orchestrator endpoint: {endpoint_key}")

    if endpoint_key == "local":
        print("Testing LM Studio connection...")
        try:
            import requests
            test_response = requests.get("http://localhost:1234/v1/models", timeout=5)
            test_response.raise_for_status()
            print("✓ LM Studio is running\n")
        except Exception as e:
            print(f"⚠ Warning: Could not connect to LM Studio: {e}")
            print("  Make sure LM Studio is running on http://localhost:1234\n")
    elif endpoint_key in getattr(config, "OPENAI_ENDPOINTS", {}):
        has_key = bool(config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"))
        status = "configured" if has_key else "missing"
        print(f"Using OpenAI endpoint '{endpoint_key}' (API key: {status})\n")
    elif endpoint_key in getattr(config, "ANTHROPIC_ENDPOINTS", {}):
        has_key = bool(config.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY"))
        status = "configured" if has_key else "missing"
        print(f"Using Anthropic endpoint '{endpoint_key}' (API key: {status})\n")
    elif endpoint_key in getattr(config, "HF_ENDPOINTS", {}):
        hf_cfg = config.HF_ENDPOINTS[endpoint_key]
        url = hf_cfg.get("url", "unknown")
        print(f"Using HuggingFace endpoint '{endpoint_key}' ({url})\n")
    else:
        print(f"⚠ Warning: Unknown orchestrator endpoint '{endpoint_key}', REPL will apply fallback behavior.\n")

    # Initialize and run REPL
    repl = REPL()

    # Start background market data refresh
    _start_market_refresh_thread()
    _start_regulatory_refresh_thread()
    _start_alert_check_thread()

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
