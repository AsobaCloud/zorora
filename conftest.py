import sys
import os

# Ensure project root is on sys.path so bare py_modules
# (config, repl, llm_client, etc.) are importable by tests.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
