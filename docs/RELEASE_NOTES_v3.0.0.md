# Zorora v3.0.0 Release Notes

**Release Date:** February 2026
**Previous Release:** v2.6.1-prod

---

## Major Features

### Data Analysis Engine

Full-stack data analysis capability — load a CSV, profile it automatically, then run arbitrary pandas/matplotlib code in a sandboxed environment, all from the REPL.

**New Slash Commands:**
```
/load <path>       Load and profile a CSV dataset
/analyze <code>    Run sandboxed Python analysis on the loaded dataset
```

### Data Profiler (`tools/data_analysis/profiler.py`)
- **Automatic Profiling** — Row/column counts, dtype detection, null analysis, numeric summaries
- **Time Series Detection** — Identifies datetime columns, computes time range, resolution, and gap count
- **ODS-E Format Detection** — Recognizes Solarman inverter exports and flags ODS-E compatibility
- **Descriptive Statistics** — Full `df.describe()` output included in profile

### Sandboxed Code Execution (`tools/data_analysis/execute.py`)
- **Secure `exec()` Sandbox** — Allowlisted builtins only (`len`, `range`, `sum`, `min`, `max`, `round`, `sorted`, `enumerate`, `zip`, `map`, `filter`, `list`, `dict`, `set`, `tuple`, `str`, `int`, `float`, `bool`, `print`, `type`, `isinstance`, `abs`, `any`, `all`)
- **Blocked Imports** — `os`, `sys`, `subprocess`, `shutil`, `importlib`, `pathlib` are prohibited
- **Pre-injected Globals** — `df` (loaded DataFrame), `pd`, `np`, `scipy.stats`, `plt` (matplotlib)
- **Smart Result Detection** — Returns typed JSON: `scalar`, `dataframe`, `series`, `list`, `dict`, `string`, `none`
- **Plot Capture** — Detects `__zorora_plot__.png` saves and returns `plot_generated: true` with file path
- **Configurable Timeout** — Default 30s, configurable via `DATA_ANALYSIS.execution_timeout`

### Load Dataset Workflow (`workflows/load_dataset.py`)
- **Three-Stage Pipeline** — Ingest/detect → Profile → Session assembly
- **Automatic Timestamp Parsing** — Detects and parses `Timestamp`, `datetime`, `date`, `time` columns
- **Session Store** — Loaded DataFrame and metadata persist in `tools.data_analysis.session` for subsequent `/analyze` calls
- **File Replacement** — Loading a new file replaces the previous session cleanly

### Nehanda Local Query (`tools/data_analysis/nehanda_local.py`)
- **Offline Policy Search** — FAISS-based vector search over local `.txt` policy document corpus
- **Sentence-Transformers Embeddings** — Uses `all-MiniLM-L6-v2` with numpy cosine-similarity fallback
- **Configurable** — Corpus dir, index cache dir, chunk size, top-k via `NEHANDA_LOCAL` config

---

## Architecture Changes

### New Module: `tools/data_analysis/`
```
tools/data_analysis/
├── __init__.py         # Package init
├── profiler.py         # profile_dataframe(df) → dict
├── execute.py          # execute_analysis(code, session_id, plot_dir) → JSON
├── session.py          # Module-level session store (get_df, set_df, clear)
└── nehanda_local.py    # nehanda_query(query, top_k, corpus_dir) → JSON
```

### New Workflow: `workflows/load_dataset.py`
- `LoadDatasetWorkflow.execute(file_path)` — CSV ingest → profile → session store

### Tool Registry Integration (`tools/registry.py`)
- Registered `execute_analysis` and `nehanda_query` in `TOOL_FUNCTIONS`, `TOOLS_DEFINITION` (OpenAI function-calling format), and `SPECIALIST_TOOLS`

### Router Integration (`simplified_router.py`)
- Added `_is_data_analysis_request()` with regex patterns for analyze/plot/calculate/DataFrame keywords
- Routes matching queries to `data_analysis` workflow

### REPL Command Processor (`engine/repl_command_processor.py`)
- Added `/load <path>` handler with usage message for missing argument
- Added `/analyze <code>` handler

### Turn Processor (`turn_processor.py`)
- Added `execute_analysis` and `nehanda_query` to parameter mapping
- Added `data_analysis` workflow handler in `process()`

### Tool Executor (`tool_executor.py`)
- Added parameter fixes: `execute_analysis: {task→code, prompt→code}`, `nehanda_query: {task→query}`

---

## Cleanup

### Legacy Files Removed
- **`tool_registry.py`** — Backward-compat shim (deprecated since v2.5.0), now deleted
- **`tool_registry_legacy.py`** — Original 3,300-line tool registry backup, now deleted
- **`config.example.py`** — Removed; `config.py` is the single source of truth

### README Updated
- Removed references to `config.example.py` copy step
- Removed `tool_registry.py` and `tool_registry_legacy.py` from directory tree

---

## Dependencies

Added to `install_requires` in `setup.py`:
- `pandas>=2.0.0`
- `numpy>=1.24.0`
- `matplotlib>=3.7.0`
- `scipy>=1.10.0`

---

## Configuration

New config sections in `config.py`:

```python
DATA_ANALYSIS = {
    "max_code_length": 10000,
    "execution_timeout": 30,
    "plot_output_dir": "plots",
}

NEHANDA_LOCAL = {
    "corpus_dir": "",
    "index_cache_dir": "",
    "embedding_model": "all-MiniLM-L6-v2",
    "chunk_size": 512,
    "top_k_default": 5,
}
```

---

## Testing

### 179 Tests — All Passing

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_data_profiler.py` | 26 | Profiler: row/col counts, dtypes, nulls, time detection, resolution, gaps, ODS-E |
| `test_execute_analysis.py` | 29 | Sandbox: result types, blocked imports, timeout, plot capture, error handling |
| `test_load_dataset.py` | 22 | Workflow: ingest, profile, session store, file replacement, timestamp parsing |
| `test_nehanda_local.py` | 20 | Local query: chunking, embedding, search, fallback, edge cases |
| `test_data_analysis_integration.py` | 30 | End-to-end: load CSV → analyze with pandas/numpy/matplotlib |
| `test_tool_executor.py` | 52 | Tool dispatch, param fixing, file ops end-to-end |

### End-to-End Integration Tests
- **Synthetic CSV tests** — Load CSV → `df.describe()`, `df.shape`, column mean, filter, numpy std, correlation, plot generation, groupby, file replacement
- **Demo data tests** — Load actual `demo-data.csv` (17,569 rows) → row count, column count, max power, time span validation

---

## Upgrade Notes

- **No breaking changes** to existing research, coding, or web UI functionality
- New dependencies (`pandas`, `numpy`, `matplotlib`, `scipy`) are added to `install_requires` — run `pip install -e .` or `pip install -r requirements.txt` to update
- Legacy `tool_registry.py` import shim is removed — use `from tools.registry import ...` instead (deprecation warning was active since v2.5.0)
- `config.example.py` is removed — edit `config.py` directly

---

## Statistics

- **New modules:** 5 (`profiler.py`, `execute.py`, `session.py`, `nehanda_local.py`, `load_dataset.py`)
- **New test files:** 5 (2,126 lines of tests)
- **Total new tests:** 179
- **Lines added:** ~2,900 (implementation + tests)
- **Lines removed:** ~3,570 (legacy registry cleanup)

---

**Full Changelog:** `git log v2.6.1-prod..v3.0.0-prod`
