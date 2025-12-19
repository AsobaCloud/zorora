"""Setup script for Zorora REPL."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="zorora",
    version="1.0.0",
    description="Multi-model orchestration REPL for local AI assistants",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Asoba",
    url="https://github.com/AsobaCloud/zorora",
    py_modules=[
        "main",
        "repl",
        "config",
        "conversation",
        "conversation_persistence",
        "llm_client",
        "tool_executor",
        "tool_registry",
        "turn_processor",
        "model_selector",
        "ui",
        "router",
        "planner",
    ],
    entry_points={
        "console_scripts": [
            "zorora=main:main",
        ],
    },
    install_requires=[
        "requests>=2.28.0",
        "rich>=13.0.0",
        "ddgs>=9.0.0",
        "beautifulsoup4>=4.11.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    include_package_data=True,
)
