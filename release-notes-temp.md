# Zorora v1.1.0 - Release Notes

## What's New

### 🎓 Academic Search Command (`/academic`)

New dedicated command for searching academic papers across multiple sources:

- **7 Academic Sources:**
  - Google Scholar (via DuckDuckGo)
  - PubMed (via DuckDuckGo)
  - CORE API (direct API with PDF download links)
  - arXiv (via DuckDuckGo)
  - bioRxiv (via DuckDuckGo)
  - medRxiv (via DuckDuckGo)
  - PubMed Central (via DuckDuckGo)

- **Sci-Hub Integration:**
  - Always checks Sci-Hub for full-text PDF access
  - Automatically tags papers with `[Full Text Available]` when found
  - Parallel checking for fast results

- **Usage:**
  ```
  /academic machine learning interpretability
  /academic quantum computing 2024
  ```

### 🔍 Enhanced Web Search

Web search now automatically includes academic sources:

- **Always includes:** Scholar and PubMed results in every web search
- **No differentiation:** Academic results blend seamlessly with web results
- **Configurable:** Set `academic_max_results` in config (default: 3 per source)

### 🎨 UI Improvements

- **Welcome screen:** Changed panel border color to tan (#D2B48C)
- **Help menu:** Updated with `/academic` command
- **Command list:** Added `/academic` to welcome screen

## Technical Improvements

### Performance

- **Parallel execution:** Academic searches run in parallel (7 sources simultaneously)
- **Parallel Sci-Hub checks:** Up to 10 concurrent Sci-Hub availability checks
- **Faster results:** Reduced search time with concurrent operations

### Reliability

- **SSL/TLS fixes:** Improved handling of TLS 1.3 protocol issues in DuckDuckGo searches
- **Error handling:** Better fallback mechanisms for failed searches
- **PMC search:** Fixed unreliable `site:` filter with keyword search + URL filtering

### Code Quality

- **Warning suppression:** Suppressed BeautifulSoup encoding warnings
- **Dependency management:** Installed beautifulsoup4 for Sci-Hub parsing
- **Code organization:** Moved deprecated files to `deprecated/` folder

## Configuration

### New Config Options

Added to `config.example.py`:

```python
ACADEMIC_SEARCH = {
    "default_max_results": 10,
    "core_api_key": "YOUR_CORE_API_KEY",
    "scihub_mirrors": [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru"
    ]
}
```

### Updated Config

- `WEB_SEARCH["academic_max_results"]`: Max Scholar/PubMed results in web search (default: 3)

## Documentation

- Updated `README.md` with `/academic` command
- Updated `COMMANDS.md` with academic search documentation
- Updated `/help` menu with new command

## Bug Fixes

- Fixed PMC search failures (replaced unreliable `site:` filter)
- Fixed SSL/TLS warnings in DuckDuckGo searches
- Suppressed BeautifulSoup encoding warnings
- Fixed result duplication in academic search output

## Breaking Changes

None - all changes are backward compatible.

## Migration Guide

No migration needed. New features are opt-in via the `/academic` command. Web search automatically includes academic sources (no configuration needed).

## Contributors

- Added CORE API integration
- Implemented parallel search execution
- Enhanced Sci-Hub integration

---

**Full Changelog:** https://github.com/AsobaCloud/zorora/compare/v1.0.0...v1.1.0
