# Plan: Fix Linting Issues in SEP-043/SEP-047 Implementation

## Objective
Fix remaining linting errors in the nearly-complete SEP-043 (Imaging→Discovery rename + grid infrastructure) and SEP-047 (market data refresh) implementations while working in plan mode (read-only).

## Scope
- Focus on linting errors only - no feature implementation or UI changes
- Files with linting issues identified from ruff check output:
  - `docs/notebooks/polymarket_insider_signal_audit_2025_2026.ipynb` (unused `cluster` variable)
  - `model_selector.py` (unused import of LLMClient)
  - Various files with bare `except` statements
  - Test files with unused imports
  - Variable naming issues

## Steps to Execute:
1. **Fix unused variable `cluster` in notebook**:
   - Remove or use the `cluster = infer_cluster(row)` assignments that are assigned but never used

2. **Fix unused import in model_selector.py**:
   - Remove the unused `from llm_client import LLMClient` import that's inside a try block

3. **Fix bare except statements**:
   - Replace bare `except:` with specific exception types (e.g., `except Exception:`)
   - Files affected: validation scripts, integration tests, image generator, intent specialist, ONA platform commands

4. **Fix unused imports in test files**:
   - Remove unused imports: `tools.market.ember_client`, `workflows.background_threads` in test_sep047.py

5. **Fix ambiguous variable name**:
   - Change variable name `l` to something more descriptive in tools/specialist/intent.py

6. **Fix type comparison**:
   - Replace `type(output1) != type(output2)` with `type(output1) is not type(output2)` or `not isinstance(output1, type(output2))`

## Validation:
- Run `ruff check .` to verify no linting errors remain
- Run relevant tests to ensure functionality is preserved
- Specifically verify SEP-043 and SEP-047 related functionality still works

## Notes:
- This plan focuses exclusively on linting fixes as requested
- No UI changes, feature additions, or logic modifications are included
- All changes should be backward compatible and preserve existing functionality
- Once linting is clean, the implementation can proceed to testing and review phases