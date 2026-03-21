"""Entry point for Claude Code-like REPL."""

import sys
import os
import logging
import threading
from repl import REPL
from config import LOGGING_LEVEL, LOGGING_FORMAT, LOG_FILE
import config
from workflows.background_threads import start_all_background_threads
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


def _start_regulatory_refresh_thread():
    """Start the regulatory refresh background thread (patchable entry point)."""
    def _loop():
        try:
            workflow = RegulatoryWorkflow()
            updated = workflow.update_all()
            if updated:
                logger.info("Regulatory refresh: updated %d sources", updated)
        except Exception as exc:
            logger.debug("Regulatory refresh failed: %s", exc)

    t = threading.Thread(target=_loop, daemon=True, name="regulatory-refresh")
    t.start()
    return t


def _start_alert_check_thread():
    """Start the alert check background thread (patchable entry point)."""
    def _loop():
        try:
            store = AlertStore()
            due = store.get_due_alerts()
            for alert in due:
                try:
                    execute_alert(alert, store)
                except Exception as exc:
                    logger.debug("Alert execution failed for %s: %s", alert.get("id"), exc)
            store.close()
        except Exception as exc:
            logger.debug("Alert check failed: %s", exc)

    t = threading.Thread(target=_loop, daemon=True, name="alert-check")
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

    # Start background data refresh threads
    start_all_background_threads()

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
