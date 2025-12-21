# /develop Workflow Architecture Plan

## Overview
Multi-step coding workflow that explores codebase, plans changes, gets user approval, executes changes, and validates with linting.

## Workflow Phases

### Phase 1: Codebase Exploration
**Purpose**: Understand existing code structure and context

**Sub-agent**: `CodebaseExplorer`
- **Input**: Current working directory path
- **Process**:
  1. Walk directory tree (exclude common ignore patterns: node_modules, .git, __pycache__, venv, etc.)
  2. Identify file types and directory structure
  3. Read and analyze key files (package.json, requirements.txt, README, main entry points)
  4. Detect framework/language patterns
  5. Map dependencies and imports
  6. Identify existing patterns (API structure, data models, utility functions)
- **Output**: Structured summary containing:
  - Project type (Node.js, Python, etc.)
  - Directory structure
  - Key files and their purposes
  - Existing patterns and conventions
  - Dependencies and tech stack
  - Entry points

**Model**: Use orchestrator model (cost-effective for file reading/analysis)

### Phase 2: Planning
**Purpose**: Create detailed implementation plan based on codebase context

**Sub-agent**: `CodePlanner`
- **Input**:
  - Codebase exploration summary
  - User's development request (from /develop command)
- **Process**:
  1. Analyze request in context of existing codebase
  2. Identify files to create/modify
  3. Determine dependencies to add
  4. Plan step-by-step implementation
  5. Consider edge cases and error handling
  6. Structure plan as ordered task list
- **Output**: Detailed plan with:
  - Overview of changes
  - Files to create (with purpose)
  - Files to modify (with specific changes)
  - Dependencies to add
  - Configuration changes
  - Step-by-step execution order
  - Testing recommendations

**Model**: Use reasoning model for better planning (qwen2.5:32b or similar)

### Phase 3: User Review & Approval
**Purpose**: Get user confirmation before making changes

**UI Interaction**:
- Display formatted plan with rich formatting
- Show three options:
  1. **Approve** - Proceed to execution
  2. **Modify** - Provide new prompt, restart planning phase
  3. **Cancel** - Abort workflow

**State Management**:
- If Modified: Loop back to Phase 2 with modified prompt + original exploration
- If Cancelled: Clean exit
- If Approved: Proceed to Phase 4

### Phase 4: Code Execution
**Purpose**: Implement the plan step-by-step

**Executor**: `CodeExecutor`
- **Input**: Approved plan + codebase summary
- **Model**: Use Codestral (specialized code generation model)
- **Process**:
  1. Execute plan tasks in order
  2. For each task:
     - If creating new file: Use `write_file` tool
     - If modifying existing file: Use `edit_file` tool (requires reading first)
     - Log each action
     - Track modified files list
  3. Show progress indicator to user
  4. Handle errors gracefully (log and continue vs. abort)
- **Output**:
  - List of modified/created files
  - Execution log
  - Any errors encountered

### Phase 5: Linting & Validation
**Purpose**: Ensure code quality before user testing

**Validator**: `CodeValidator`
- **Process**:
  1. Detect linter based on project type:
     - Node.js: eslint, prettier
     - Python: ruff, black, pylint
     - Go: gofmt, golint
     - Rust: rustfmt, clippy
  2. For each modified file:
     - Run appropriate linter
     - Collect lint results
     - If errors: Attempt auto-fix (if linter supports it)
     - Re-lint after fix
  3. Report final status
- **Output**:
  - Per-file lint status
  - Auto-fixes applied
  - Remaining issues (if any)
  - Overall pass/fail status

### Phase 6: Completion & Handoff
**Purpose**: Present results to user for testing

**UI Display**:
- Summary of changes made
- Files created/modified (with line counts)
- Lint status (all passed/issues remaining)
- Next steps recommendation
- Option to rollback (git checkout) if needed

## Implementation Architecture

### File Structure
```
zorora/
├── workflows/
│   ├── __init__.py
│   ├── develop_workflow.py       # Main workflow orchestrator
│   ├── codebase_explorer.py      # Phase 1: Exploration
│   ├── code_planner.py            # Phase 2: Planning
│   └── code_executor.py           # Phase 4: Execution
├── tools/
│   └── code_tools.py              # write_file, edit_file, lint_file tools
└── ui.py                          # Add display_plan() method
```

### State Management
Use a `DevelopWorkflowState` class to track:
```python
@dataclass
class DevelopWorkflowState:
    request: str                    # Original user request
    working_directory: str          # CWD at invocation
    codebase_summary: Optional[Dict] = None
    plan: Optional[Dict] = None
    modified_files: List[str] = field(default_factory=list)
    execution_log: List[str] = field(default_factory=list)
    current_phase: str = "exploration"
    status: str = "in_progress"  # in_progress, completed, cancelled, failed
```

### Tool Registry Additions
New tools needed:
1. **write_file(path: str, content: str)** - Create new file
2. **edit_file(path: str, changes: List[Edit])** - Modify existing file
3. **lint_file(path: str, linter: Optional[str])** - Run linter on file
4. **detect_project_type(directory: str)** - Identify project framework

### Integration with REPL
Add to `repl.py`:
```python
# /develop <request> - Multi-step code development workflow
elif cmd_lower.startswith("/develop "):
    request = command[9:].strip()
    if not request:
        self.ui.console.print("[red]Usage: /develop <development request>[/red]")
        return None
    self.ui.console.print(f"[cyan]Starting development workflow...[/cyan]")

    # Import and run workflow
    from workflows.develop_workflow import DevelopWorkflow
    workflow = DevelopWorkflow(
        tool_executor=self.tool_executor,
        llm_client=self.llm_client,
        ui=self.ui
    )
    return workflow.execute(request, os.getcwd())
```

## User Experience Flow

```
User: /develop a node.js backend for calling google search api

[Phase 1: Exploration]
🔍 Exploring codebase in /Users/shingi/project...
  ✓ Found package.json (Node.js project)
  ✓ Analyzed 15 files across 4 directories
  ✓ Detected Express.js framework

[Phase 2: Planning]
📋 Creating implementation plan...
  ✓ Plan created with 5 tasks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPLEMENTATION PLAN

Overview:
Add Google Search API integration to existing Express.js backend

Changes Required:
1. Create new file: src/api/search.js
   - Express router for /api/search endpoint
   - Google Custom Search API integration
   - Error handling and rate limiting

2. Modify: package.json
   - Add dependency: googleapis@^118.0.0
   - Add dependency: dotenv@^16.0.0

3. Create new file: .env.example
   - Template for required API keys

4. Modify: src/app.js
   - Import and mount search router
   - Add /api/search route

5. Create new file: src/middleware/validateSearch.js
   - Input validation middleware
   - Query sanitization

Dependencies to install:
- googleapis (Google APIs Node.js client)
- dotenv (Environment variable management)

Testing recommendations:
- Test with valid search queries
- Test rate limiting
- Test error handling (invalid API key, network errors)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[A]pprove  [M]odify  [C]ancel: a

[Phase 4: Execution]
⚙️  Executing plan...
  ✓ Created src/api/search.js (78 lines)
  ✓ Modified package.json
  ✓ Created .env.example (5 lines)
  ✓ Modified src/app.js
  ✓ Created src/middleware/validateSearch.js (32 lines)

[Phase 5: Linting]
🔧 Validating code quality...
  ✓ src/api/search.js - Passed
  ✓ package.json - Passed
  ✓ src/app.js - Passed (auto-fixed formatting)
  ✓ src/middleware/validateSearch.js - Passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ DEVELOPMENT COMPLETE

Summary:
- Files created: 3
- Files modified: 2
- Total lines: 115
- Lint status: ✓ All passed

Modified files:
  src/api/search.js (new, 78 lines)
  src/middleware/validateSearch.js (new, 32 lines)
  .env.example (new, 5 lines)
  package.json (modified)
  src/app.js (modified)

Next steps:
1. Run: npm install (to install new dependencies)
2. Configure: Copy .env.example to .env and add API keys
3. Test: curl http://localhost:3000/api/search?q=test

Ready for testing!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Error Handling

### Exploration Phase Errors
- Empty directory: Warn and proceed with minimal context
- Permission errors: Skip inaccessible files, log warning
- No recognizable project: Proceed anyway, treat as new project

### Planning Phase Errors
- LLM timeout: Retry once, then fail gracefully
- Invalid plan structure: Prompt LLM to reformat

### Execution Phase Errors
- File write errors: Log error, ask user if should continue
- Edit conflicts: Show diff, ask user how to proceed
- Model errors: Retry task once, then skip with warning

### Linting Phase Errors
- Linter not found: Skip linting for that file type, warn user
- Lint failures: Report issues, don't block completion
- Auto-fix errors: Report original lint error, continue

## Configuration
Add to `config.py`:
```python
# Development Workflow
DEVELOP_EXPLORER_MODEL = "qwen/qwen2.5:32b"  # Model for exploration
DEVELOP_PLANNER_MODEL = "qwen/qwen2.5:32b"   # Model for planning
DEVELOP_CODER_MODEL = "codestral"            # Model for code generation
DEVELOP_MAX_FILES_EXPLORE = 100              # Max files to analyze
DEVELOP_ENABLE_LINTING = True                # Enable lint phase
DEVELOP_AUTO_FIX_LINT = True                 # Auto-fix lint errors if possible
```

## Security Considerations
1. **File Access**: Only operate within working directory and subdirectories
2. **Destructive Operations**: Never delete files, only create/edit
3. **Git Safety**: Recommend git status/diff before making changes
4. **Sensitive Files**: Warn if modifying .env, credentials, etc.
5. **User Confirmation**: Always require approval before writing files

## Future Enhancements
- [ ] Git integration (auto-commit after completion)
- [ ] Test generation (create unit tests for new code)
- [ ] Dependency installation (auto-run npm install, pip install)
- [ ] Interactive debugging (if linting fails, offer to debug)
- [ ] Multi-language support (better detection and handling)
- [ ] Context preservation (save workflow state for resume)
- [ ] Rollback capability (undo all changes if something breaks)

## Design Decisions
1. **Git Repository Required**: Yes - workflow will check for git repo and refuse to run if not present
2. **Large Codebases**: Full exploration with warning if >1000 files
3. **Auto-Install Dependencies**: Yes - auto-run npm install / pip install after execution phase
4. **Backups**: Rely on git (no .bak files) - recommend user check git status first
5. **Model Selection**:
   - Exploration: Orchestrator model (cost-effective for file reading)
   - Planning: Reasoning model (better quality plans)
   - Execution: Codestral (specialized for code generation)

## Success Metrics
- User can go from request to working code in one command
- Plan approval rate > 80% (plan quality)
- Lint pass rate > 90% (code quality)
- Average execution time < 5 minutes
- User satisfaction with generated code quality
