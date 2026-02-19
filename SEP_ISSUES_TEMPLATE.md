# SEP Issue List: Data Analysis Feature Gap Closure

Source spec: `/Users/shingi/Downloads/Zorora_Data_Analysis_Feature_Spec.docx`
Scope date: February 2026 spec vs current repository implementation.

## SEP-DA-001: Implement Real ODS-E Transform Execution

- Problem
Current `load_dataset` detects likely ODS-E/Solarman columns but does not execute actual OEM transform pipelines.

- Spec Requirement
Stage 1 requires known OEM CSVs to be automatically transformed to ODS-E via `odse` package and surfaced to user as transformed output.

- Current Behavior
`LoadDatasetWorkflow._try_odse_transform()` only checks package availability and returns boolean; no transform output is applied to `df`.

- Proposed Change
Add a transform adapter in `workflows/load_dataset.py` that:
1. Detects supported OEM formats via odse harness.
2. Executes transform and replaces working `df` with normalized ODS-E frame.
3. Stores transform metadata (OEM, mapped fields, row counts) in session metadata.
4. Updates load summary with detection + transform status.

- Acceptance Criteria
1. Known OEM sample files produce ODS-E normalized schema in session `df`.
2. Load summary includes OEM name and transformed row count.
3. If transform fails validation, workflow falls back gracefully to non-ODS-E path.
4. Tests cover at least one positive transform and one fallback case.

- Dependencies
`odse` package and test fixtures for supported OEM formats.

- Out of Scope
Custom OEM parser authoring beyond odse-supported formats.

## SEP-DA-002: Add Generic CSV Column Mapping + Confirmation

- Problem
Generic labeled CSVs are loaded directly without a user-confirmed mapping step to ODS-E-like fields.

- Spec Requirement
Stage 1 requires column mapping suggestions for recognizable but non-OEM datasets, with explicit user confirmation and pass-through for unmapped fields.

- Current Behavior
No interactive/non-interactive mapping suggestion pipeline exists in `/load` flow.

- Proposed Change
Add mapping suggestion engine that:
1. Heuristically maps timestamp/kWh/power/energy/error columns.
2. Presents proposed mapping in REPL output.
3. Supports confirmation command path (`/load --confirm-map` or follow-up confirm command).
4. Persists both mapped canonical fields and original unmapped metadata columns.

- Acceptance Criteria
1. Generic dataset triggers mapping suggestion output.
2. Confirmed mapping updates canonical analysis schema.
3. Unconfirmed mapping keeps raw mode without data loss.
4. Tests cover suggestion quality and confirmation flow.

- Dependencies
REPL command extension for confirmation UX.

- Out of Scope
GUI wizard and fully manual per-column editor in v1.

## SEP-DA-003: Inject Dataset Context into LLM System Prompt per Session

- Problem
Data profile/schema/sample are stored in session metadata, but system-context assembly is not guaranteed in model prompt construction for all analysis turns.

- Spec Requirement
Stage 3 requires one-time session context assembly including profile, schema, sample rows, available tools, and ODS-E context.

- Current Behavior
Context exists in `tools.data_analysis.session` but explicit prompt-layer injection path is incomplete/implicit.

- Proposed Change
Create deterministic context builder and inject into turn processing when dataset session is active:
1. Build compact context block from `profile`, `schema`, and sample rows.
2. Append ODS-E transform notes when present.
3. Include tool guidance (`execute_analysis`, `nehanda_query`, `web_search`) and grounding instruction.
4. Ensure context is added once per session and refreshed on new `/load`.

- Acceptance Criteria
1. Active data session causes context block in model messages.
2. Reloaded dataset replaces prior context.
3. Token footprint stays within target budget (spec range).
4. Tests verify context inclusion and replacement behavior.

- Dependencies
Turn/message assembly path in `/Users/shingi/Workbench/zorora/turn_processor.py` and LLM client message builder.

- Out of Scope
Prompt optimization experiments across providers.

## SEP-DA-004: Complete Plot Rendering UX and Artifact Persistence

- Problem
`execute_analysis` detects sentinel plot file and returns path, but full inline image rendering and standardized artifact persistence workflow is incomplete.

- Spec Requirement
Plot outputs should render inline where terminal supports it and always persist to session output directory with fallback path.

- Current Behavior
Tool returns `plot_generated` and `plot_path`; no guaranteed Rich terminal protocol rendering path in current flow.

- Proposed Change
1. Add display adapter in REPL/UI layer to render PNG for iTerm2/Kitty/Sixel when available.
2. Copy sentinel to session output directory with stable naming.
3. Return user-facing artifact location in assistant response.
4. Preserve text-only fallback for unsupported terminals.

- Acceptance Criteria
1. Plot-producing analysis displays image inline on supported terminals.
2. Plot persists under session output directory regardless of inline support.
3. Fallback path is shown when inline rendering unavailable.
4. Tests verify artifact persistence and result metadata.

- Dependencies
UI terminal capability detection and session artifact directory conventions.

- Out of Scope
Advanced chart gallery/history browser.

## SEP-DA-005: Package and Bootstrap Local Nehanda Policy Corpus

- Problem
`nehanda_query` works only when a corpus directory is supplied; no shipped corpus/index bootstrap pipeline exists in repo packaging.

- Spec Requirement
Local policy retrieval should operate from curated shipped corpus, with first-run index bootstrap and source metadata.

- Current Behavior
No default packaged corpus under docs/policy and no first-run bootstrap wiring in runtime startup.

- Proposed Change
1. Define default corpus location and include policy text/pdf assets in package data.
2. Implement startup/bootstrap check for index availability.
3. Build/rebuild index when corpus changes.
4. Wire `/analyst` and tool calls to default local corpus when no explicit path provided.

- Acceptance Criteria
1. Fresh install can execute `nehanda_query` without manual corpus path argument.
2. Returned chunks include source metadata.
3. Missing/invalid corpus produces actionable error with remediation.
4. Tests cover default-path success and bootstrap path.

- Dependencies
Packaging updates in `setup.py` and policy corpus content curation.

- Out of Scope
Live remote Bedrock KB mode as default.

## SEP-DA-006: Align Dependency and Installation Surface

- Problem
Core data-analysis dependencies are split between `setup.py` and `requirements.txt`; spec dependencies for odse/vector retrieval are not fully declared in install paths.

- Spec Requirement
Implementation plan assumes installable dependencies for ODS-E transform and local retrieval stack.

- Current Behavior
`setup.py` includes pandas/numpy/scipy/matplotlib; `requirements.txt` currently omits these and omits `odse`, `sentence-transformers`, and FAISS strategy declaration.

- Proposed Change
1. Normalize dependency definitions (or document authoritative source).
2. Add optional extras groups (e.g., `data`, `policy`) for heavier dependencies.
3. Update docs with minimal and full install commands.
4. Validate CI/test matrix for both minimal and full profiles.

- Acceptance Criteria
1. One documented install path consistently enables v1 feature set.
2. Optional extras cleanly gate heavy dependencies.
3. CI verifies expected behavior for each install profile.

- Dependencies
Packaging strategy decision.

- Out of Scope
Provider-specific binary wheel troubleshooting guides.

## SEP-DA-007: Add Cross-Domain Orchestration Acceptance Tests

- Problem
Unit/integration tests cover core tools, but explicit acceptance tests for data + policy + web cross-domain synthesis behavior are missing.

- Spec Requirement
High-value cross-domain queries should validate data claim via analysis, retrieve policy context, and synthesize grounded response.

- Current Behavior
Discrete tests exist for data analysis and Nehanda query; orchestrated multi-tool grounding acceptance path is not explicitly validated.

- Proposed Change
Add scenario-level tests that assert:
1. Data claim verification via `execute_analysis`.
2. Policy retrieval via `nehanda_query`.
3. Optional current context via `web_search`.
4. Final response includes explicit grounding to data and cited policy source chunk.

- Acceptance Criteria
1. At least two end-to-end scenarios pass in CI.
2. Regression tests fail when grounding or tool chaining breaks.
3. Test fixtures are deterministic and offline-safe (with mocked web layer where required).

- Dependencies
Test harness for multi-tool orchestration.

- Out of Scope
Benchmark scoring of answer quality beyond deterministic assertions.

## Suggested Execution Order
1. SEP-DA-001
2. SEP-DA-002
3. SEP-DA-003
4. SEP-DA-004
5. SEP-DA-005
6. SEP-DA-006
7. SEP-DA-007
