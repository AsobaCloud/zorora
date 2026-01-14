# Zorora Tool Improvement Action Plan

> **Created**: January 2026
> **Status**: Ready for Implementation
> **Context**: Derived from MCP migration analysis and offline coding reliability analysis

---

## Overview

Six improvements identified that address real pain points:

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add `/deep` command to terminal UI | Small | High - feature parity with Web UI |
| 2 | Improve file editing reliability | Medium | **Critical** - enables offline coding |
| 3 | Add retry loop to CodeExecutor | Medium | High - error recovery |
| 4 | Rename `use_codestral` → `use_coding_agent` | Small | Medium - clarity and accuracy |
| 5 | Complete tool registry migration | Medium | Medium - code hygiene |
| 6 | Full file context in edit prompts | Small | Medium - accuracy improvement |

---

## Task 1: Add `/deep` Command to Terminal UI

### Problem
Deep research engine (multi-source aggregation, credibility scoring, cross-referencing, synthesis) is only accessible via Web UI. Terminal users are limited to the simpler `/search` workflow.

### Current State
```
Web UI:     ResearchEngine + DeepResearchWorkflow (full capability)
Terminal:   ResearchWorkflow (newsroom + web + synthesis only)
```

### Solution
Add `/deep <query>` command to `repl.py` that invokes `DeepResearchWorkflow`.

### Implementation

**File: `repl.py`**

Add after the `/academic` handler (~line 320):

```python
# /deep <query> - Deep research with credibility scoring
elif cmd_lower.startswith("/deep "):
    query = command[6:].strip()  # Remove "/deep "
    if not query:
        self.ui.console.print("[red]Usage: /deep <query>[/red]")
        self.ui.console.print("[dim]Example: /deep impact of AI on renewable energy markets[/dim]")
        return None

    self.ui.console.print(f"[cyan]Starting deep research (academic + web + newsroom + credibility scoring)...[/cyan]")

    from workflows.deep_research.workflow import DeepResearchWorkflow
    from engine.research_engine import ResearchEngine

    workflow = DeepResearchWorkflow(max_depth=1)
    state = workflow.execute(query)

    # Format output
    result = state.synthesis if state.synthesis else "No synthesis generated"

    # Optionally save to research engine
    research_engine = ResearchEngine()
    research_id = research_engine.save_research(state)

    result += f"\n\n[dim]Research saved: {research_id}[/dim]"

    if result:
        self.turn_processor.last_specialist_output = result
        self.conversation.add_assistant_message(content=result)

    return (result, 0.0) if result else None
```

**File: `repl.py` → `_show_help()`**

Add to workflow commands section:
```python
[cyan]/deep <query>[/cyan]          - Deep research with credibility scoring (academic + web + newsroom)
```

**File: `COMMANDS.md`**

Add documentation for `/deep` command with examples.

### Testing
1. Run `zorora` in terminal
2. Execute `/deep impact of quantum computing on cryptography`
3. Verify output includes:
   - Source aggregation from multiple sources
   - Credibility scores
   - Synthesis with citations
   - Research ID for later retrieval

---

## Task 2: Improve File Editing Reliability

### Problem
Current `edit_file` implementation is fragile—edits fail silently, models hallucinate file contents, and there's no recovery mechanism. This is the primary blocker for reliable offline coding.

### Current State (tool_registry_legacy.py:260-308)
```python
def edit_file(path, old_string, new_string, working_directory=None):
    if old_string not in content:
        return "Error: String not found in file."
    if occurrences > 1:
        return "Error: String appears {n} times."
    # No read enforcement, no line numbers, no retry
```

### Implementation

#### 2.1 Add Read-Before-Edit Enforcement

**File: `tool_executor.py`**

```python
class ToolExecutor:
    def __init__(self, registry: ToolRegistry, ui=None):
        self.registry = registry
        self.ui = ui
        self.working_directory = Path.cwd()
        self.files_read_this_session = set()  # NEW

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        # Track file reads
        if tool_name == "read_file":
            path = arguments.get("path", "")
            normalized = self._normalize_path(path)
            self.files_read_this_session.add(normalized)

        # Enforce read-before-edit
        if tool_name == "edit_file":
            path = arguments.get("path", "")
            normalized = self._normalize_path(path)
            if normalized not in self.files_read_this_session:
                return "Error: You must read the file before editing. Use read_file first to see current content."

        # ... rest of execute ...

    def _normalize_path(self, path: str) -> str:
        """Normalize path for comparison."""
        resolved = self._resolve_path(path)
        return str(Path(resolved).resolve())

    def clear_read_cache(self):
        """Clear read tracking (call on /clear or new session)."""
        self.files_read_this_session.clear()
```

#### 2.2 Add Line Numbers to File Reads

**File: `tool_registry_legacy.py` → `read_file()`**

```python
def read_file(path: str, working_directory=None, show_line_numbers=True) -> str:
    # ... existing validation ...

    try:
        content = file_path.read_text()

        if show_line_numbers:
            lines = content.splitlines()
            # Format like cat -n (6-char line number + tab + content)
            numbered = []
            for i, line in enumerate(lines, 1):
                numbered.append(f"{i:6d}\t{line}")
            return "\n".join(numbered)
        else:
            return content

    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
```

#### 2.3 Add `replace_all` Option

**File: `tool_registry_legacy.py` → `edit_file()`**

```python
def edit_file(path: str, old_string: str, new_string: str,
              replace_all: bool = False, working_directory=None) -> str:
    # ... existing validation ...

    if old_string not in content:
        # Helpful error: show similar strings
        similar = _find_similar_substring(content, old_string)
        if similar:
            return f"Error: Exact string not found. Similar text found:\n---\n{similar[:300]}\n---\nMake sure whitespace and indentation match exactly."
        return "Error: String not found. Use read_file to see current content."

    occurrences = content.count(old_string)

    if occurrences > 1 and not replace_all:
        # Show where occurrences are
        locations = _find_line_numbers(content, old_string)
        return f"Error: String appears {occurrences} times at lines {locations}. Either:\n1. Include more surrounding context to make it unique, or\n2. Set replace_all=True to replace all occurrences"

    if replace_all:
        new_content = content.replace(old_string, new_string)
        file_path.write_text(new_content)
        return f"OK: Replaced {occurrences} occurrence(s) in '{path}'"
    else:
        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content)
        return f"OK: Replaced 1 occurrence in '{path}'"


def _find_similar_substring(content: str, target: str, context_chars: int = 100) -> str:
    """Find similar substring in content (handles whitespace differences)."""
    # Normalize whitespace for comparison
    normalized_target = ' '.join(target.split())
    normalized_content = ' '.join(content.split())

    if normalized_target in normalized_content:
        # Find approximate location
        idx = normalized_content.find(normalized_target)
        # Map back to original content (rough approximation)
        start = max(0, idx - context_chars)
        end = min(len(content), idx + len(target) + context_chars)
        return content[start:end]
    return ""


def _find_line_numbers(content: str, substring: str) -> str:
    """Find line numbers where substring appears."""
    lines = content.splitlines()
    locations = []
    for i, line in enumerate(lines, 1):
        if substring in line or (len(substring) > len(line) and line in substring):
            locations.append(str(i))
    return ", ".join(locations[:10]) + ("..." if len(locations) > 10 else "")
```

#### 2.4 Update Tool Definition

**File: `tool_registry_legacy.py` → `TOOLS_DEFINITION`**

```python
{
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "Edit a file by replacing exact string match. You MUST read the file first with read_file. The old_string must match exactly including whitespace and indentation.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact string to find and replace (must be unique or use replace_all)"
                },
                "new_string": {
                    "type": "string",
                    "description": "String to replace with"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: false)",
                    "default": false
                }
            },
            "required": ["path", "old_string", "new_string"]
        }
    }
}
```

### Testing
1. Try to edit without reading first → Should get clear error
2. Edit with whitespace mismatch → Should get helpful similar-text hint
3. Edit string that appears 3 times → Should get line numbers and options
4. Use `replace_all=True` → Should replace all occurrences

---

## Task 3: Add Retry Loop to CodeExecutor

### Problem
When an edit fails in `/develop`, the workflow logs the error and moves on. The model never sees its own errors and can't self-correct.

### Current State (workflows/code_executor.py:147-192)
```python
def _execute_edit_file(self, task, codebase_summary):
    # Generate edit
    result = self.tool_executor.execute("use_codestral", {...})
    edit_instructions = self._extract_edit_instructions(result, current_content)

    # Try once, fail if error
    edit_result = edit_file(file_path, old_content, new_content, ...)
    if edit_result.startswith("Error"):
        return edit_result  # NO RETRY
```

### Implementation

**File: `workflows/code_executor.py`**

```python
def _execute_edit_file(self, task: Dict, codebase_summary: Dict, max_retries: int = 3) -> str:
    """
    Execute file edit task with retry loop.

    Returns:
        Result message
    """
    file_path = task.get("file_path")
    if not file_path:
        return "Error: No file_path specified"

    full_path = Path(self.working_directory) / file_path
    if not full_path.exists():
        return f"Error: File {file_path} does not exist"

    last_error = None

    for attempt in range(max_retries):
        try:
            # Always re-read file (content may have changed in previous attempt)
            current_content = full_path.read_text(encoding='utf-8')

            # Build prompt (include error context on retry)
            if attempt == 0:
                edit_prompt = self._build_file_edit_prompt(task, current_content, codebase_summary)
            else:
                edit_prompt = self._build_retry_edit_prompt(
                    task=task,
                    current_content=current_content,
                    codebase_summary=codebase_summary,
                    previous_error=last_error,
                    attempt=attempt
                )

            # Generate edit
            result = self.tool_executor.execute("use_codestral", {
                "code_context": edit_prompt
            })

            # Extract instructions
            edit_instructions = self._extract_edit_instructions(result, current_content)

            if not edit_instructions:
                last_error = "Could not parse edit instructions from model response"
                logger.warning(f"Attempt {attempt+1}: {last_error}")
                continue

            old_content = edit_instructions["old"]
            new_content = edit_instructions["new"]

            # Apply edit
            edit_result = edit_file(file_path, old_content, new_content, self.working_directory)

            if not edit_result.startswith("Error"):
                # Success!
                self.modified_files.append(file_path)
                if attempt > 0:
                    logger.info(f"Edit succeeded on attempt {attempt+1}")
                return edit_result

            # Failed - capture error for next attempt
            last_error = edit_result
            logger.warning(f"Attempt {attempt+1} failed: {edit_result}")

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt+1} exception: {e}")

    return f"Error: Failed after {max_retries} attempts. Last error: {last_error}"


def _build_retry_edit_prompt(self, task: Dict, current_content: str,
                              codebase_summary: Dict, previous_error: str,
                              attempt: int) -> str:
    """Build prompt for retry attempt with error context."""
    file_path = task.get("file_path")
    description = task.get("description", "")

    # Add line numbers for precision
    numbered_content = self._add_line_numbers(current_content)

    prompt = f"""RETRY ATTEMPT {attempt + 1}: Your previous edit failed.

ERROR: {previous_error}

FILE: {file_path}

CURRENT CONTENT (with line numbers - use these for reference):
{numbered_content}

TASK: {description}

IMPORTANT:
1. The OLD_CODE must match EXACTLY what's in the file (including whitespace)
2. Copy the exact text from the file above, preserving indentation
3. If the string appears multiple times, include more context to make it unique

Output in this format:
OLD_CODE:
```
[exact code to replace - copy from file above]
```

NEW_CODE:
```
[replacement code]
```"""

    return prompt


def _add_line_numbers(self, content: str) -> str:
    """Add line numbers to content."""
    lines = content.splitlines()
    numbered = [f"{i:4d} | {line}" for i, line in enumerate(lines, 1)]
    return "\n".join(numbered)
```

### Testing
1. Intentionally cause edit to fail (whitespace mismatch)
2. Verify retry prompt includes error context
3. Verify second/third attempt succeeds
4. Verify logging shows retry attempts

---

## Task 4: Rename `use_codestral` → `use_coding_agent`

### Problem
Function is named after a specific model (Codestral) but is actually a model-agnostic coding agent that can use any configured model.

### Files to Update (10 files + Task 2/3 changes)

| File | Changes |
|------|---------|
| `tool_registry_legacy.py` | Function definition, SPECIALIST_TOOLS list |
| `tools/registry.py` | Import, TOOL_FUNCTIONS dict, SPECIALIST_TOOLS list |
| `tool_executor.py` | Special handling for UI injection, parameter fixing |
| `turn_processor.py` | `_execute_specialist_tool()` param mapping |
| `simplified_router.py` | Routing target |
| `system_prompt.txt` | Tool description for LLM |
| `docs/ARCHITECTURE.md` | Documentation |
| `docs/MCP_MIGRATION_ANALYSIS.md` | Already updated |
| `docs/DEEP_RESEARCH_IMPLEMENTATION.md` | Documentation |
| `workflows/code_executor.py` | Tool invocation |

### Implementation Steps

1. **Rename function in `tool_registry_legacy.py`**:
   ```python
   def use_coding_agent(code_context: str, ui=None) -> str:
   ```

2. **Update SPECIALIST_TOOLS**:
   ```python
   SPECIALIST_TOOLS = [
       "use_coding_agent",  # was use_codestral
       ...
   ]
   ```

3. **Add backward-compatible alias in `tools/registry.py`**:
   ```python
   TOOL_ALIASES: Dict[str, str] = {
       "use_codestral": "use_coding_agent",  # Backward compat
       ...
   }
   ```

4. **Update all references** in the 10 files listed above

5. **Update tool definition**:
   ```python
   {
       "type": "function",
       "function": {
           "name": "use_coding_agent",
           "description": "Generate code using the configured coding model. Supports planning, implementation, and code review.",
           ...
       }
   }
   ```

### Testing
1. Run existing `/code` command - should work unchanged
2. Verify alias resolves `use_codestral` → `use_coding_agent`
3. Check logs show new function name

---

## Task 5: Complete Tool Registry Migration

### Problem
`tools/registry.py` imports most functions from `tool_registry_legacy.py`. This duplication adds complexity and makes the codebase harder to maintain.

### Current State
```
tools/
├── registry.py              # Central registry (imports from legacy)
├── research/                # MIGRATED (Phase 1)
│   ├── academic_search.py
│   ├── web_search.py
│   └── newsroom.py
└── (future modules)

tool_registry_legacy.py      # 2800+ lines, contains everything else
```

### Migration Plan

**Phase 2: File Operations** → `tools/file_ops/`
```
tools/file_ops/
├── __init__.py
├── read.py          # read_file
├── write.py         # write_file
├── edit.py          # edit_file
├── directory.py     # list_files, make_directory, get_working_directory
└── utils.py         # _resolve_path, _validate_path
```

**Phase 3: Shell Operations** → `tools/shell/`
```
tools/shell/
├── __init__.py
├── execute.py       # run_shell
└── patch.py         # apply_patch
```

**Phase 4: Specialist Models** → `tools/specialist/`
```
tools/specialist/
├── __init__.py
├── coding_agent.py  # use_coding_agent (renamed from use_codestral)
├── reasoning.py     # use_reasoning_model
├── search_model.py  # use_search_model
├── intent.py        # use_intent_detector
├── energy.py        # use_energy_analyst
└── client.py        # _create_specialist_client
```

**Phase 5: Image Tools** → `tools/image/`
```
tools/image/
├── __init__.py
├── analyze.py       # analyze_image
├── generate.py      # generate_image
└── search.py        # web_image_search
```

**Phase 6: Cleanup**
- Update `tools/registry.py` to import from new modules
- Delete `tool_registry_legacy.py`
- Update any remaining imports

### Implementation Order

1. **Phase 2 first** - File operations are self-contained
2. **Phase 4 second** - Specialist models (includes Task 2 rename)
3. **Phase 3 third** - Shell operations
4. **Phase 5 fourth** - Image tools
5. **Phase 6 last** - Cleanup and delete legacy

### Per-Module Migration Pattern

For each function being migrated:

1. Create new module file with function
2. Add to `tools/registry.py` imports
3. Remove from legacy imports in registry
4. Test functionality
5. Repeat until module complete
6. Delete corresponding code from legacy file

### Testing Strategy
- Run full test suite after each module migration
- Verify REPL commands still work
- Check Web UI still functions
- Validate tool definitions are correct

---

## Task 6: Full File Context in Edit Prompts

### Problem
Current `_build_file_edit_prompt` truncates files to 3000 chars, losing context for large files. This causes models to generate incorrect edits.

### Current State (workflows/code_executor.py:238-280)
```python
def _build_file_edit_prompt(self, task, current_content, codebase_summary):
    content_preview = current_content
    if len(current_content) > 3000:
        content_preview = current_content[:1500] + "\n... [middle truncated] ...\n" + current_content[-1500:]
```

### Implementation

**File: `workflows/code_executor.py`**

```python
def _build_file_edit_prompt(self, task: Dict, current_content: str, codebase_summary: Dict) -> str:
    """Build prompt for editing existing file."""
    file_path = task.get("file_path")
    description = task.get("description", "")
    details = task.get("details", "")

    # Smart truncation based on file size
    if len(current_content) <= 8000:
        # Small-medium files: include full content with line numbers
        content_section = self._add_line_numbers(current_content)
        truncation_note = ""
    elif len(current_content) <= 20000:
        # Large files: include relevant sections
        content_section = self._smart_truncate_for_edit(current_content, task)
        truncation_note = "\n[Note: File truncated to relevant sections. If you need to see other parts, ask to read specific line ranges.]"
    else:
        # Very large files: focused extraction
        content_section = self._extract_edit_region(current_content, task)
        truncation_note = "\n[Note: Large file - showing only region around edit target. Full file is {len(current_content)} chars.]"

    prompt = f"""Modify an existing file in a {codebase_summary.get('project_type', 'software')} project.

FILE: {file_path}

CURRENT CONTENT:
{content_section}
{truncation_note}

MODIFICATION NEEDED: {description}

DETAILS: {details}

REQUIREMENTS:
1. The OLD_CODE must match EXACTLY what's in the file (including whitespace/indentation)
2. Copy the text precisely from the content above
3. If string appears multiple times, include enough context to make it unique
4. Preserve existing code style

Output in this format:
OLD_CODE:
```
[exact code to replace - copy from above]
```

NEW_CODE:
```
[replacement code]
```"""

    return prompt


def _smart_truncate_for_edit(self, content: str, task: Dict) -> str:
    """Smart truncation that preserves edit-relevant context."""
    lines = content.splitlines()
    numbered = []

    # Always include first 50 lines (imports, class definitions)
    for i, line in enumerate(lines[:50], 1):
        numbered.append(f"{i:4d} | {line}")

    if len(lines) > 100:
        numbered.append("     | ... (middle section) ...")

    # Include last 50 lines
    if len(lines) > 50:
        start = max(50, len(lines) - 50)
        for i, line in enumerate(lines[start:], start + 1):
            numbered.append(f"{i:4d} | {line}")

    return "\n".join(numbered)


def _extract_edit_region(self, content: str, task: Dict) -> str:
    """Extract region around likely edit target for very large files."""
    description = task.get("description", "").lower()
    lines = content.splitlines()

    # Try to find relevant function/class
    target_keywords = []
    for word in description.split():
        if len(word) > 3 and word.isalnum():
            target_keywords.append(word)

    # Find lines containing keywords
    relevant_lines = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in target_keywords):
            # Include context around match
            start = max(0, i - 20)
            end = min(len(lines), i + 30)
            relevant_lines.extend(range(start, end))

    if relevant_lines:
        relevant_lines = sorted(set(relevant_lines))
        numbered = []
        prev_line = -1
        for i in relevant_lines:
            if prev_line >= 0 and i > prev_line + 1:
                numbered.append("     | ...")
            numbered.append(f"{i+1:4d} | {lines[i]}")
            prev_line = i
        return "\n".join(numbered)

    # Fallback to head/tail
    return self._smart_truncate_for_edit(content, task)
```

### Testing
1. Edit a 500-line file → Should see full content with line numbers
2. Edit a 1000-line file → Should see relevant sections
3. Edit a 5000-line file → Should see focused extraction around target

---

## Implementation Order

Recommended sequence:

```
Week 1: Tasks 1-2
        ├── Task 1: /deep command (small, high impact)
        └── Task 2: File editing reliability (critical for offline coding)
            ├── 2.1 Read-before-edit enforcement
            ├── 2.2 Line numbers in file reads
            ├── 2.3 replace_all option
            └── 2.4 Actionable error messages

Week 2: Tasks 3, 6
        ├── Task 3: Retry loop in CodeExecutor (enables error recovery)
        └── Task 6: Full file context (improves edit accuracy)

Week 3: Task 4
        └── Task 4: Rename use_codestral → use_coding_agent
            (Can be done standalone or with Task 5 Phase 4)

Weeks 4-7: Task 5 (registry migration)
        ├── Phase 2: File ops
        ├── Phase 3: Shell ops
        ├── Phase 4: Specialist (includes rename if not done in Week 3)
        ├── Phase 5: Image tools
        └── Phase 6: Cleanup
```

---

## Success Criteria

### Task 1: `/deep` Command
- [ ] Command accessible in terminal REPL
- [ ] Output includes credibility scores
- [ ] Research persisted to SQLite
- [ ] Documentation updated

### Task 2: File Editing Reliability
- [ ] Read-before-edit enforcement active
- [ ] Line numbers shown in file reads
- [ ] `replace_all` option works
- [ ] Error messages show similar text / line numbers
- [ ] Tool definition updated

### Task 3: Retry Loop
- [ ] Failed edits trigger retry (up to 3 attempts)
- [ ] Retry prompt includes error context
- [ ] Line numbers in retry prompts
- [ ] Logging shows retry attempts

### Task 4: Rename
- [ ] All files updated to `use_coding_agent`
- [ ] Backward-compatible alias works
- [ ] No broken imports
- [ ] Documentation updated

### Task 5: Migration
- [ ] `tool_registry_legacy.py` deleted
- [ ] All tools in modular `tools/` structure
- [ ] No functionality regression
- [ ] Cleaner import structure

### Task 6: Full File Context
- [ ] Small files (<8KB) show full content
- [ ] Medium files show smart truncation
- [ ] Large files show focused extraction
- [ ] Line numbers always included

---

## Notes

- Tasks 2, 3, 6 are **critical for offline coding reliability**
- Task 4 can be combined with Task 5 Phase 4 for efficiency
- Each phase should be a separate commit for easy rollback
- Web UI and REPL should be tested after each change
- For best offline coding results, use 32B+ models (Q4_K_M quantization)

---

## Related Documentation

- `docs/OFFLINE_CODING_RELIABILITY_ANALYSIS.md` - Detailed analysis of Claude Code patterns
- `docs/MCP_MIGRATION_ANALYSIS.md` - Why MCP was not adopted
