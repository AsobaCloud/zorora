"""Gunicorn configuration for Zorora production deployment."""

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
