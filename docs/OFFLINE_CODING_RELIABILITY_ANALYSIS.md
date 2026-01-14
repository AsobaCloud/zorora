# Offline Coding Reliability Analysis

> **Goal**: Achieve Claude Code-like reliability for offline coding with local models
> **Date**: January 2026

---

## Executive Summary

The gap between Zorora's `/develop` workflow and Claude Code isn't primarily about model quality—it's about **tool design** and **feedback loops**. Claude Code's editing reliability comes from:

1. Strict read-before-edit enforcement
2. Precise string matching with disambiguation
3. Immediate error feedback that helps the model self-correct
4. Iterative retry loops until success

Zorora's current `edit_file` implementation lacks these safeguards, making edits fragile even with capable models.

---

## Current State Analysis

### Zorora's `/develop` Workflow

```
/develop <request>
    │
    ├─ Phase 0: Pre-flight (git check)
    ├─ Phase 1: Exploration (CodebaseExplorer)
    ├─ Phase 2: Planning (CodePlanner)
    ├─ Phase 3: User Approval
    ├─ Phase 4: Execution (CodeExecutor)
    ├─ Phase 5: Linting
    └─ Phase 6: Dependency Installation
```

**The workflow structure is sound.** The problem is in Phase 4: Execution.

### Current `edit_file` Implementation

```python
def edit_file(path: str, old_string: str, new_string: str, working_directory=None) -> str:
    # ...
    if old_string not in content:
        return "Error: String not found in file."

    occurrences = content.count(old_string)
    if occurrences > 1:
        return "Error: String appears {n} times. Be more specific."

    new_content = content.replace(old_string, new_string, 1)
    file_path.write_text(new_content)
```

**Problems:**

| Issue | Impact |
|-------|--------|
| No read-before-edit enforcement | Model may hallucinate file contents |
| Exact string match only | Whitespace/indentation mismatch = failure |
| No line number context | Can't disambiguate multiple occurrences |
| Single-shot execution | Edit fails → workflow fails |
| Error messages don't help model self-correct | No guidance on what went wrong |
| File truncation in prompts (3000 chars) | Model loses context for large files |

### How Claude Code's Edit Tool Works

From the system prompt you're using now:

```
Edit tool requirements:
- You must use Read tool at least once before editing
- Preserve exact indentation from file content
- old_string must be unique in file (or use replace_all)
- Never include line number prefix in old_string/new_string
```

**Key differences:**

| Claude Code | Zorora |
|-------------|--------|
| Read file required before edit | No enforcement |
| Line numbers shown for context | No line numbers |
| `replace_all` option for bulk changes | Single occurrence only |
| Immediate error → retry in same turn | Error → workflow fails |
| Model sees full file (or smart truncation) | 3000 char truncation |

---

## Root Cause: The Model-Tool Contract

Claude Code works because of a **tight feedback loop**:

```
Model reads file
    ↓
Model proposes edit (old_string, new_string)
    ↓
Tool validates:
  - Does old_string exist?
  - Is it unique (or replace_all=true)?
  - Does indentation match?
    ↓
If error → Model sees error → Model adjusts → Retry
If success → Continue
```

Zorora's loop is **open**, not closed:

```
CodeExecutor builds prompt (truncated file content)
    ↓
Codestral generates OLD_CODE/NEW_CODE
    ↓
edit_file() attempts replacement
    ↓
If error → Log error → Move to next task (NO RETRY)
```

**The model never sees its own errors.**

---

## Proposed Improvements

### Tier 1: Quick Wins (High Impact, Low Effort)

#### 1.1 Enforce Read-Before-Edit

Add validation that file was read in current session before allowing edit:

```python
class ToolExecutor:
    def __init__(self):
        self.files_read_this_session = set()

    def execute(self, tool_name, arguments):
        if tool_name == "read_file":
            path = arguments.get("path")
            self.files_read_this_session.add(self._normalize_path(path))

        elif tool_name == "edit_file":
            path = arguments.get("path")
            if self._normalize_path(path) not in self.files_read_this_session:
                return "Error: You must read the file before editing. Use read_file first."
```

#### 1.2 Add Line Numbers to File Reads

When reading files, include line numbers (like Claude Code):

```python
def read_file(path: str, ...) -> str:
    content = file_path.read_text()
    lines = content.splitlines()

    # Format with line numbers (cat -n style)
    numbered = []
    for i, line in enumerate(lines, 1):
        numbered.append(f"{i:6d}\t{line}")

    return "\n".join(numbered)
```

This helps the model:
- Reference specific locations
- Navigate large files
- Be precise about edit locations

#### 1.3 Improve Error Messages

Make errors actionable:

```python
def edit_file(path, old_string, new_string, ...):
    if old_string not in content:
        # Find similar strings to help model
        similar = _find_similar_strings(content, old_string, threshold=0.8)
        if similar:
            return f"Error: Exact string not found. Did you mean:\n{similar[0][:200]}"
        return "Error: String not found. Read the file again with read_file to see current content."

    if occurrences > 1:
        # Show line numbers where string appears
        locations = _find_all_locations(content, old_string)
        return f"Error: String appears {occurrences} times at lines {locations}. Include more context to disambiguate."
```

### Tier 2: Structural Improvements (Medium Effort)

#### 2.1 Add Retry Loop to CodeExecutor

```python
def _execute_edit_file(self, task, codebase_summary, max_retries=3) -> str:
    for attempt in range(max_retries):
        # Generate edit
        result = self.tool_executor.execute("use_codestral", {"code_context": edit_prompt})
        edit_instructions = self._extract_edit_instructions(result, current_content)

        # Try to apply
        edit_result = edit_file(file_path, old_content, new_content, ...)

        if not edit_result.startswith("Error"):
            return edit_result  # Success

        # Failed - build retry prompt with error context
        edit_prompt = self._build_retry_prompt(
            original_task=task,
            previous_attempt=edit_instructions,
            error_message=edit_result,
            current_content=current_content  # Re-read file
        )

        logger.info(f"Edit failed, attempt {attempt+1}/{max_retries}: {edit_result}")

    return f"Error: Failed after {max_retries} attempts. Last error: {edit_result}"
```

#### 2.2 Add `replace_all` Option

```python
def edit_file(path, old_string, new_string, replace_all=False, working_directory=None):
    occurrences = content.count(old_string)

    if occurrences == 0:
        return "Error: String not found..."

    if occurrences > 1 and not replace_all:
        locations = _find_all_locations(content, old_string)
        return f"Error: Found {occurrences} occurrences at lines {locations}. Use replace_all=True for bulk replacement."

    if replace_all:
        new_content = content.replace(old_string, new_string)
        return f"OK: Replaced {occurrences} occurrences"
    else:
        new_content = content.replace(old_string, new_string, 1)
        return f"OK: Replaced 1 occurrence"
```

#### 2.3 Full File Context in Edit Prompts

Remove the 3000 char truncation that loses context:

```python
def _build_file_edit_prompt(self, task, current_content, codebase_summary):
    # For files under 10KB, include full content
    if len(current_content) < 10000:
        content_section = current_content
    else:
        # Smart truncation: keep imports, class definitions, and target area
        content_section = self._smart_truncate(current_content, task)

    # Add line numbers
    numbered_content = self._add_line_numbers(content_section)

    prompt = f"""...
CURRENT CONTENT (with line numbers):
{numbered_content}
..."""
```

### Tier 3: Advanced Capabilities (Higher Effort)

#### 3.1 Diff Preview Before Apply

Show the model what will change before committing:

```python
def edit_file_preview(path, old_string, new_string, working_directory=None):
    """Preview an edit without applying it."""
    # ... validation ...

    # Generate unified diff
    import difflib
    old_lines = content.splitlines(keepends=True)
    new_content = content.replace(old_string, new_string, 1)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path)
    return "".join(diff)
```

#### 3.2 Fuzzy Matching for Whitespace

Handle indentation/whitespace mismatches:

```python
def edit_file(path, old_string, new_string, fuzzy=False, ...):
    if old_string not in content and fuzzy:
        # Normalize whitespace and try again
        normalized_old = _normalize_whitespace(old_string)
        normalized_content = _normalize_whitespace(content)

        if normalized_old in normalized_content:
            # Find the actual string in original content
            actual_old = _find_actual_match(content, old_string)
            if actual_old:
                return edit_file(path, actual_old, new_string, fuzzy=False, ...)
```

#### 3.3 Semantic Edit Operations

Add higher-level edit operations:

```python
def edit_file_insert_after(path, anchor_string, new_content, working_directory=None):
    """Insert new content after a specific line/string."""

def edit_file_insert_before(path, anchor_string, new_content, working_directory=None):
    """Insert new content before a specific line/string."""

def edit_file_replace_function(path, function_name, new_implementation, working_directory=None):
    """Replace an entire function definition."""
```

---

## Implementation Priority

| Priority | Improvement | Effort | Impact |
|----------|-------------|--------|--------|
| **1** | Read-before-edit enforcement | Low | High - prevents hallucinated edits |
| **2** | Line numbers in file reads | Low | High - helps precision |
| **3** | Actionable error messages | Low | Medium - helps self-correction |
| **4** | Retry loop in CodeExecutor | Medium | High - enables recovery |
| **5** | `replace_all` option | Low | Medium - enables bulk changes |
| **6** | Full file context | Medium | Medium - improves accuracy |
| **7** | Diff preview | Medium | Low - nice to have |
| **8** | Fuzzy matching | Medium | Low - edge case handling |

**Recommended Phase 1 (1 week):**
- Items 1, 2, 3, 5 (all low effort, high cumulative impact)

**Recommended Phase 2 (1 week):**
- Item 4 (retry loop - fundamental reliability improvement)
- Item 6 (full context - accuracy improvement)

---

## Model Quality Considerations

Even with perfect tools, model quality matters. For offline coding:

| Model Size | Realistic Capability |
|------------|---------------------|
| 4B | Simple edits, single-file changes, bug fixes |
| 8B | Multi-file awareness, refactoring, new features |
| 32B | Complex architecture changes, large codebases |
| 70B+ | Claude Code-level capability |

**Recommendation**: For serious offline coding, target 32B models minimum. The tool improvements above will help any model, but smaller models will still struggle with complex multi-file changes.

**LM Studio optimization**: Run Q4_K_M quantization of 32B models. On M3 MacBook Air with 24GB RAM, this gives reasonable performance with good quality.

---

## Testing the Improvements

### Test Case 1: Simple Edit
```
/develop add a docstring to the main() function in main.py
```
Expected: Should work reliably with current 4B model after improvements.

### Test Case 2: Multi-occurrence Edit
```
/develop rename the variable 'data' to 'user_data' in auth.py
```
Expected: Should prompt for `replace_all` or handle multiple occurrences.

### Test Case 3: Large File Edit
```
/develop add error handling to the process_request function in api_handler.py (800 lines)
```
Expected: Should maintain context and edit precisely.

### Test Case 4: Failed Edit Recovery
```
/develop add logging to config.py
```
Intentionally cause first edit to fail (whitespace mismatch), verify retry succeeds.

---

## Conclusion

The path to Claude Code-like reliability offline is:

1. **Fix the tools** (read-before-edit, line numbers, errors, replace_all)
2. **Add retry loops** (let model self-correct)
3. **Preserve context** (don't truncate files aggressively)
4. **Use capable models** (32B+ for complex work)

The model is only as good as the tools let it be. Even Claude struggles with bad tool design.
