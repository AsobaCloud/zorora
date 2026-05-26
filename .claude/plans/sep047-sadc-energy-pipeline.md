# SEP-047: SADC Energy Data Pipeline

Implements SEP-048.

## Objective

Make all 27 tests in `tests/test_sep047.py` pass by adding HTTP fetch capability to the Eskom client, creating an Ember API client, replacing World Bank global macro series with SADC electricity indicators, extracting background refresh threads to a shared module, and adding data freshness timestamps to the Global View UI cards.

## Scope

- /Users/shingi/Workbench/zorora/tools/market/eskom_client.py
- /Users/shingi/Workbench/zorora/tools/market/ember_client.py
- /Users/shingi/Workbench/zorora/tools/market/series.py
- /Users/shingi/Workbench/zorora/workflows/market_workflow.py
- /Users/shingi/Workbench/zorora/workflows/background_threads.py
- /Users/shingi/Workbench/zorora/web_main.py
- /Users/shingi/Workbench/zorora/main.py
- /Users/shingi/Workbench/zorora/config.py
- /Users/shingi/Workbench/zorora/ui/web/app.py
- /Users/shingi/Workbench/zorora/ui/web/templates/index.html

## Justification

The test file `tests/test_sep047.py` defines 27 tests across 7 test classes covering 5 success criteria. The user explicitly asked to make these tests pass by implementing the minimal code needed. All changes follow existing code patterns (module-level functions, `List[Tuple[str, float]]` returns, provider dispatch in `MarketWorkflow._update_series`).

Documentation consulted:
- `tests/test_sep047.py` (the test file defining expected behavior)
- `tools/market/eskom_client.py` (existing CSV parser using local file I/O)
- `tools/market/series.py` (existing SERIES_CATALOG with MarketSeries dataclass)
- `workflows/market_workflow.py` (existing provider dispatch in `_update_series`)
- `config.py` (existing ESKOM, WORLD_BANK_INDICATORS configs)
- `main.py` (existing inline background threads)
- `web_main.py` (currently no background threads)
- `ui/web/app.py` (existing `get_market_latest` endpoint)
- `ui/web/templates/index.html` (existing `renderDatasetCards` function)

## Success Criteria

All 27 tests in `tests/test_sep047.py` pass when run with `python -m pytest tests/test_sep047.py -v`. Zero failures, zero errors. The changes are minimal and follow existing patterns.

## Validation

### Sources consulted
- `tests/test_sep047.py` lines 1-708: All 27 tests read and analyzed
- `tools/market/eskom_client.py`: Current `_parse_csv` uses `open()` for local files only
- `tools/market/series.py`: Current catalog has 6 global macro WB series in "development" group
- `config.py`: ESKOM config has local file paths, no URLs; WORLD_BANK_INDICATORS has `default_country: "all"`
- `workflows/market_workflow.py`: `_update_series` dispatches by provider, no ember handling
- `main.py`: Three inline `_start_*_thread` functions
- `web_main.py`: No background threads at all
- `ui/web/app.py` line 878-911: `get_market_latest` has no freshness field
- `ui/web/templates/index.html` line 4112: Card shows `latest_date` but no freshness

### Evidence for each fix
1. **Eskom HTTP**: Test mocks `requests.get` and passes URL to `fetch_demand_observations` — need `_parse_csv` to detect URL and use `requests.get` instead of `open()`
2. **Ember client**: Tests import `tools.market.ember_client`, call a `fetch*` function with country code "ZAF", expect `List[Tuple[str, float]]` return
3. **SADC WB series**: Tests check specific IDs (`NY.GDP.MKTP.CD` etc.) are NOT in catalog, and that WB series have electricity keywords and non-"development" group
4. **Background threads**: Tests import `workflows.background_threads`, call `start*` function, verify it creates threads; `web_main.py` and `main.py` must reference the module
5. **Freshness**: Tests inspect `get_market_latest` source for freshness field names; template must contain freshness indicators

### Verified vs assumed
- Verified: All test assertions, existing code patterns, existing function signatures
- Assumed: Nothing — all changes are driven directly by test assertions

### Known gaps
- None for test-passing. The Ember API format is mocked in tests so the real API shape doesn't matter here.

## Objective Verification

```
python -m pytest tests/test_sep047.py -v
```
