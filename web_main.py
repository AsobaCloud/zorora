"""
Zorora Web UI entry point.
Usage: python web_main.py
"""

from ui.web.app import app

if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=False)
