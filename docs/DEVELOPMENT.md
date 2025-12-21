# Development Workflow (`/develop`)

## Overview

The `/develop` command provides a multi-step code development workflow that:
1. Explores your codebase to understand structure and patterns
2. Creates a detailed implementation plan
3. Gets your approval before making changes
4. Executes the plan step-by-step
5. Validates code quality with linting

## Usage

```
/develop <development request>
```

**Examples:**
```
/develop add REST API endpoint for user authentication
/develop refactor database connection to use pooling
/develop create a new React component for user profile
```

## Requirements

- **Git repository**: Must be run in a git repository (enables rollback if needed)
- **Working directory**: Run from your project root directory

## Workflow Phases

### Phase 1: Codebase Exploration

**What happens:**
- Walks directory tree (excludes: node_modules, .git, __pycache__, venv, etc.)
- Identifies file types and directory structure
- Reads and analyzes key files (package.json, requirements.txt, README, main entry points)
- Detects framework/language patterns
- Maps dependencies and imports
- Identifies existing patterns (API structure, data models, utility functions)

**Output:** Structured summary of your codebase:
- Project type (Node.js, Python, etc.)
- Directory structure
- Key files and their purposes
- Existing patterns and conventions
- Dependencies and tech stack
- Entry points

**Model:** Orchestrator model (cost-effective for file reading/analysis)

### Phase 2: Planning

**What happens:**
- Analyzes your request in context of existing codebase
- Identifies files to create/modify
- Determines dependencies to add
- Plans step-by-step implementation
- Considers edge cases and error handling
- Structures plan as ordered task list

**Output:** Detailed plan with:
- Overview of changes
- Files to create (with purpose)
- Files to modify (with specific changes)
- Dependencies to add
- Configuration changes
- Step-by-step execution order
- Testing recommendations

**Model:** Reasoning model for better planning quality

### Phase 3: User Review & Approval

**What happens:**
- Displays formatted plan with rich formatting
- Shows three options:
  1. **Approve** - Proceed to execution
  2. **Modify** - Provide new prompt, restart planning phase
  3. **Cancel** - Abort workflow

**Important:** Always review the plan carefully before approving!

### Phase 4: Code Execution

**What happens:**
- Executes plan tasks in order
- Creates new files
- Modifies existing files
- Shows progress indicator
- Handles errors gracefully

**Model:** Codestral specialist model (optimized for code generation)

### Phase 5: Linting & Validation

**What happens:**
- Detects linter based on project type:
  - Node.js: eslint, prettier
  - Python: ruff, black, pylint
  - Go: gofmt, golint
  - Rust: rustfmt, clippy
- Runs linter on each modified file
- Attempts auto-fix if linter supports it
- Reports final status

**Output:**
- Per-file lint status
- Auto-fixes applied
- Remaining issues (if any)
- Overall pass/fail status

### Phase 6: Completion & Handoff

**What happens:**
- Summary of changes made
- Files created/modified (with line counts)
- Lint status (all passed/issues remaining)
- Next steps recommendation
- Option to rollback (git checkout) if needed

## Example Session

```
[1] ⚙ > /develop add node.js backend for calling google search api

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

## Best Practices

### Before Running `/develop`

1. **Commit your work**: Ensure you have a clean git state
   ```bash
   git status
   git commit -am "Save current work"
   ```

2. **Be specific**: Provide clear, detailed requests
   - Good: "Add REST API endpoint for user authentication with JWT tokens"
   - Less clear: "Add auth"

3. **Review the plan**: Always review the plan carefully before approving
   - Check files to be created/modified
   - Verify dependencies
   - Consider edge cases

### During Planning Phase

1. **Review carefully**: Read through the entire plan
2. **Check file paths**: Ensure files are created in correct locations
3. **Verify dependencies**: Check if dependencies are appropriate
4. **Consider edge cases**: Think about error handling and validation

### After Execution

1. **Review generated code**: Check the code quality and logic
2. **Run tests**: Execute your test suite if available
3. **Install dependencies**: Run `npm install` or `pip install` as needed
4. **Test functionality**: Manually test the new features
5. **Check git diff**: Review changes with `git diff`

### If Something Goes Wrong

1. **Use git rollback**: If changes break something, use git to revert
   ```bash
   git checkout -- .
   ```

2. **Modify and retry**: Use "Modify" option to refine the plan
3. **Cancel and restart**: Cancel and provide a more specific request

## Error Handling

### Exploration Phase Errors

- **Empty directory**: Warns and proceeds with minimal context
- **Permission errors**: Skips inaccessible files, logs warning
- **No recognizable project**: Proceeds anyway, treats as new project

### Planning Phase Errors

- **LLM timeout**: Retries once, then fails gracefully
- **Invalid plan structure**: Prompts LLM to reformat

### Execution Phase Errors

- **File write errors**: Logs error, asks user if should continue
- **Edit conflicts**: Shows diff, asks user how to proceed
- **Model errors**: Retries task once, then skips with warning

### Linting Phase Errors

- **Linter not found**: Skips linting for that file type, warns user
- **Lint failures**: Reports issues, doesn't block completion
- **Auto-fix errors**: Reports original lint error, continues

## Security Considerations

1. **File Access**: Only operates within working directory and subdirectories
2. **Destructive Operations**: Never deletes files, only creates/edits
3. **Git Safety**: Recommends git status/diff before making changes
4. **Sensitive Files**: Warns if modifying .env, credentials, etc.
5. **User Confirmation**: Always requires approval before writing files

## Configuration

Development workflow settings in `config.py`:

```python
# Development Workflow
DEVELOP_EXPLORER_MODEL = "qwen/qwen2.5:32b"  # Model for exploration
DEVELOP_PLANNER_MODEL = "qwen/qwen2.5:32b"   # Model for planning
DEVELOP_CODER_MODEL = "codestral"            # Model for code generation
DEVELOP_MAX_FILES_EXPLORE = 100              # Max files to analyze
DEVELOP_ENABLE_LINTING = True                # Enable lint phase
DEVELOP_AUTO_FIX_LINT = True                 # Auto-fix lint errors if possible
```

## Limitations

- **Large codebases**: Full exploration with warning if >1000 files
- **Git required**: Workflow requires git repository
- **Single request**: One development request per `/develop` command
- **No test generation**: Doesn't automatically create unit tests
- **No auto-install**: Doesn't automatically run `npm install` or `pip install`

## Tips for Better Results

1. **Provide context**: Include relevant details about your requirements
2. **Mention patterns**: Reference existing code patterns you want to follow
3. **Specify frameworks**: Mention frameworks/libraries you're using
4. **Include constraints**: Mention any constraints or requirements
5. **Be iterative**: Start with small changes, then build up

## Future Enhancements

Planned improvements:
- Git integration (auto-commit after completion)
- Test generation (create unit tests for new code)
- Dependency installation (auto-run npm install, pip install)
- Interactive debugging (if linting fails, offer to debug)
- Multi-language support (better detection and handling)
- Context preservation (save workflow state for resume)
- Rollback capability (undo all changes if something breaks)
