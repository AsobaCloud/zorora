"""
Zorora Web UI entry point.
Usage: python web_main.py
"""

from ui.web.app import app
from workflows.background_threads import start_all_background_threads

if __name__ == '__main__':
    start_all_background_threads()
    app.run(host='localhost', port=5000, debug=False)
