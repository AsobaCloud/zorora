"""Gunicorn configuration for Zorora production deployment."""

import os
import threading

bind = "0.0.0.0:5000"

# Single worker: background threads use module-level state; multiple workers
# would each have separate state, breaking data refresh and in-memory caches.
workers = 1

# Deep research and synthesis requests can exceed the default 30s timeout.
timeout = 120

# Use threads for lightweight concurrency within the single worker.
threads = 4

# Log to stdout/stderr so Docker captures output via `docker logs`.
accesslog = "-"
errorlog = "-"
loglevel = "info"


def post_worker_init(worker):
    """Start background refresh threads after the worker is ready to serve."""
    from workflows.background_threads import start_all_background_threads
    start_all_background_threads()
    # Market warm must not run synchronously here: reading every series from SQLite
    # on EFS can exceed the ALB target health interval and fail the deployment
    # (see prod rollout for commit 060730c — fixed by deferring warm off the init path).
    if os.environ.get("ZORORA_SKIP_MARKET_WARM", "").lower() in ("1", "true", "yes"):
        return
    from ui.web.app import warm_market_latest_cache

    threading.Thread(
        target=warm_market_latest_cache,
        daemon=True,
        name="market-latest-warm",
    ).start()
