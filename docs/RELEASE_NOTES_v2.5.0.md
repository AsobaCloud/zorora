# Zorora v2.5.0 Release Notes

**Release Date:** January 2025
**Previous Release:** v2-prod

---

## Major Features

### Ona Platform Integration
- **Remote ML Commands** - Execute ML model observation workflows from Zorora terminal
- **Model Lifecycle Management** - List challengers, compare models, promote/rollback
- **Audit Logging** - Track all model changes with full audit trail
- **Dual Authentication** - Support for Bearer token and AWS IAM authentication
- **End-to-End Validation** - Comprehensive validation script for Zorora ↔ Ona Platform connectivity

**Available Commands:**
```
/ml-list-challengers <customer_id>     - List challenger models
/ml-show-metrics <model_id>            - Show model evaluation metrics
/ml-diff <challenger> <production>     - Compare models
/ml-promote <customer> <model> <reason> - Promote to production
/ml-rollback <customer> <reason>       - Rollback to previous
/ml-audit-log <customer_id>            - View audit history
```

### Enhanced /code File Editing
- **Auto-Detection** - Automatically detects existing files in your prompt
- **Direct Edit Workflow** - Reads file → generates OLD_CODE/NEW_CODE → applies edit_file
- **Retry Loop** - Up to 3 attempts with error context for self-correcting edits
- **No Planning Phase** - Fast, direct edits (bypasses planning for simple changes)

**Examples:**
```
/code update script.py from "goodbye" to "hello"
/code fix the typo in utils.py line 15
/code change config.json to use port 8080
```

### Beautiful Progress Display
- **Hierarchical Tool Visualization** - Tree-style display showing tool execution flow
- **Real-time Progress** - Live updates during multi-step operations
- **Timing Information** - Per-tool execution times
- **Status Indicators** - Visual checkmarks and spinners

```
Research: latest AI developments...
├── ✓ Completed get_newsroom_headlines (2.1s)
├── ✓ Completed web_search (3.8s)
└── ◐ Running use_reasoning_model...
```

### Boxed Input UI
- **prompt_toolkit Integration** - Modern terminal input with Application/Frame/Layout
- **Visual Input Box** - Clear input area with borders
- **Improved UX** - Better cursor handling and input feedback

---

## New Capabilities

### /deep Command
- **Terminal Deep Research** - Access deep research workflow from REPL
- **Full Feature Parity** - Same capabilities as Web UI research
- **Academic + Web + Newsroom** - Multi-source synthesis with citations

### Modular Tool Registry (Complete)
- **19 Tools Migrated** - All tools now in modular `tools/` structure
- **5 Categories** - research, file_ops, shell, specialist, image
- **Backward Compatibility** - Legacy `tool_registry.py` shim with deprecation warning

```
tools/
├── registry.py          # Central registry
├── research/            # academic_search, web_search, newsroom
├── file_ops/            # read, write, edit, directory ops
├── shell/               # run_shell, apply_patch
├── specialist/          # coding, reasoning, search, intent, energy
└── image/               # analyze, generate, search
```

### Model-Agnostic Coding
- **Renamed** - `use_codestral` → `use_coding_agent`
- **Provider Flexibility** - Works with any configured coding model
- **Specialist Client Factory** - Unified client creation for all providers

---

## Architecture Changes

### Ona Platform Module
- **`zorora/commands/Ona_platform.py`** - Command registration and execution
- **`zorora/remote_command.py`** - Remote command protocol
- **`zorora/http_client.py`** - HTTP client with IAM support

### Tool Registry Structure
```
tools/
├── file_ops/
│   ├── utils.py         # Path resolution & validation
│   ├── read.py          # read_file (with line numbers)
│   ├── write.py         # write_file
│   ├── edit.py          # edit_file (with replace_all)
│   └── directory.py     # make_directory, list_files, get_working_directory
├── specialist/
│   ├── client.py        # Specialist client factory
│   ├── coding.py        # use_coding_agent (planning + generation)
│   └── ...
└── ...
```

### Turn Processor Enhancements
- **File Detection** - `_detect_file_in_input()` for edit workflow routing
- **Code Edit Execution** - `_execute_code_edit()` with retry loop
- **Edit Prompt Building** - OLD_CODE/NEW_CODE format with line numbers

---

## Improvements

### File Editing Reliability
- **Line Numbers by Default** - `read_file` includes line numbers for reference
- **replace_all Parameter** - Edit all occurrences in a file
- **Better Error Messages** - Shows similar text and line numbers on mismatch
- **Read-Before-Edit Enforcement** - Tool executor validates file was read first

### Code Executor
- **Retry Loop** - Up to 3 attempts with error context
- **Smart Truncation** - Keyword-based region extraction for large files
- **Line Numbers in Prompts** - Precise matching for edits

### SQLite Threading
- **Thread Safety** - Fixed threading issues in storage layer
- **Connection Management** - Proper connection handling per thread

### Source Display
- **Improved Formatting** - Better source citation display
- **Progress Feedback** - Real-time status during research

---

## Bug Fixes

- Fixed Ona `ml-` commands not working with leading `/` prefix
- Fixed SQLite threading issues causing intermittent failures
- Fixed `/code` generating scripts instead of using `edit_file` for existing files
- Fixed tool registry import errors from empty `__init__.py` files
- Fixed backward-compat shim not re-exporting individual tool functions

---

## Documentation

### Cleanup
- Moved 21 implementation plans/internal docs to `docs/deprecated/` (gitignored)
- Streamlined to 6 essential public docs

### Updated Docs
- **ARCHITECTURE.md** - Added `/code` edit workflow diagram
- **WORKFLOWS.md** - Updated Code Workflow with file editing mode
- **COMMANDS.md** - Updated `/code` with file editing examples
- **README.md** - Updated to v2.3.0, added workflow comparison table

---

## Migration Notes

### Breaking Changes
- `use_codestral` renamed to `use_coding_agent` (alias provided)
- Import from `tools.registry` instead of `tool_registry` (deprecation warning)

### New Environment Variables
```bash
# Ona Platform (optiOnal)
Ona_API_BASE_URL    # API endpoint
Ona_API_TOKEN       # Bearer token
Ona_USE_IAM         # Use IAM auth instead of token
ZORORA_ACTOR        # Actor identity for audit
```

---

## Statistics

- **Commits since v2-prod:** 13
- **New Modules:** 3 (zorora/commands, zorora/remote_command, zorora/http_client)
- **Tools Migrated:** 19 tools to modular structure
- **Internal Docs Archived:** 21 files moved to deprecated

---

## What's Next

- Test `/code` file editing with various models
- Expand Ona platform command coverage
- Add more file detection patterns
- Improve retry logic with better error parsing

---

**Full Changelog:** `git log v2-prod..HEAD`
