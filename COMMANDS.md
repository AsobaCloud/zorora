# Zorora Command Reference

Complete reference for all Zorora slash commands and workflows.

## Table of Contents

- [Workflow Commands](#workflow-commands)
  - [/search](#search)
  - [/ask](#ask)
  - [/code](#code)
  - [/analyst](#analyst)
  - [/image](#image)
  - [/vision](#vision)
  - [/develop](#develop)
- [System Commands](#system-commands)
  - [/models](#models)
  - [/config](#config)
  - [/history](#history)
  - [/resume](#resume)
  - [/save](#save)
  - [/clear](#clear)
  - [/visualize](#visualize)
  - [/help](#help)
- [Natural Language Queries](#natural-language-queries)

---

## Workflow Commands

Commands that force specific workflows, bypassing automatic routing.

### /search

**Force research workflow with multi-source synthesis**

```bash
/search <query>
```

**What it does:**
1. Fetches newsroom headlines (if available, filters by relevance)
2. Searches the web (Brave Search API + DuckDuckGo fallback)
3. Synthesizes findings from both sources with citations
4. Returns comprehensive answer with source URLs

**When to use:**
- When you want to ensure web search is used (bypasses auto-routing)
- For current events or time-sensitive information
- When you need multiple source verification

**Examples:**
```bash
/search latest developments in renewable energy policy
/search bitcoin vs gold price movements in 2025
/search major AI trends in South America
```

**Output format:**
- Synthesized answer with inline citations ([Newsroom], [Web])
- Source URLs listed at the end
- Mentions of domain names for web results

**Configuration:**
- Newsroom: 90 days back, max 25 relevant articles
- Web search: Brave API (primary) + DuckDuckGo (fallback)
- Parallel search enabled
- Results cached (1 hour for general queries, 24 hours for stable topics)

---

### /ask

**Force conversational mode without web search**

```bash
/ask <query>
```

**What it does:**
- Routes directly to reasoning model
- No web search, no tool calls
- Single-turn response based on model's knowledge
- Fast response for follow-up questions

**When to use:**
- Follow-up questions about previous responses
- Meta conversations about output format
- Questions that don't require current information
- Clarifications or explanations

**Examples:**
```bash
/ask can you explain that more simply?
/ask what did you mean by "virtual power plant"?
/ask how would I implement that in Python?
```

**Model used:** Reasoning model (qwen2.5:32b or configured alternative)

**Note:** Model knowledge cutoff may be outdated for current events. Use `/search` for time-sensitive queries.

---

### /code

**Code generation or file editing**

```bash
/code <prompt>
```

**What it does:**
- **File editing:** If an existing file is mentioned, reads it and applies targeted edits
- **Code generation:** If no file is detected, generates new code with planning phase

**File Editing Mode (auto-detected):**
- Detects file paths in your prompt (e.g., "script.py", "config.json")
- Reads file with line numbers
- Uses OLD_CODE/NEW_CODE format for precise edits
- Applies `edit_file` with retry loop (up to 3 attempts)
- No planning phase (fast, direct edit)

**Code Generation Mode:**
- Planning phase with user approval
- Generates code with explanations
- Returns formatted code blocks

**When to use:**
- Quick single-file edits
- Writing functions, classes, or scripts
- Code refactoring
- Algorithm implementation

**Examples:**
```bash
# File editing (file detected)
/code update script.py from "goodbye world" to "hello world"
/code fix the typo in utils.py line 15
/code change config.json to use port 8080

# Code generation (no file detected)
/code write a function to parse JSON files with error handling
/code create a REST API endpoint for user authentication
```

**vs /develop:**
- Use `/code` for quick single-file edits or snippets
- Use `/develop` for multi-file features needing codebase exploration

**Model used:** Codestral (local or HuggingFace endpoint)
- Local: qwen/qwen3-vl-4b (fast, basic)
- HF: Qwen2.5-Coder-32B-Instruct (high quality, slower)

**Saving generated output:**
```bash
> /code write a CSV parser
[Code generated...]
> /save csv_parser.py
Saved to: csv_parser.py
```

---

### /analyst

**Query EnergyAnalyst RAG for energy policy documents**

```bash
/analyst <query>
```

**What it does:**
- Routes to EnergyAnalyst RAG system
- Searches policy documents (FERC orders, ISO/RTO filings, regulations)
- Returns answers with document citations
- No web search (uses local policy database only)

**When to use:**
- Energy policy questions
- Regulatory requirements
- FERC order interpretations
- ISO/RTO market rules

**Examples:**
```bash
/analyst FERC Order 2222 requirements for battery storage
/analyst CAISO demand response program eligibility
/analyst what are the capacity market rules in PJM?
```

**Requirements:**
- EnergyAnalyst API server must be running (http://localhost:8000)
- See [EnergyAnalyst setup](https://huggingface.co/asoba/EnergyAnalyst-v0.1)

**Output format:**
- Policy analysis with document citations
- References to specific FERC orders, ISO/RTO documents
- Regulatory context and interpretations

---

### /image

**Generate image with FLUX (text-to-image)**

```bash
/image <prompt>
```

**What it does:**
- Generates image using FLUX.1-schnell model
- Text-to-image generation
- Returns image file path and displays image
- Fast generation (~5-15 seconds)

**When to use:**
- Creating visualizations
- Generating concept art
- Illustrating ideas
- Design mockups

**Examples:**
```bash
/image a futuristic solar farm at sunset
/image minimalist logo for an AI research company
/image detailed technical diagram of a battery storage system
```

**Model used:** black-forest-labs/FLUX.1-schnell
- Requires HuggingFace endpoint or local GPU
- Configure via `/models` command

**Output:**
- Image saved to working directory
- Filename: `flux_output_<timestamp>.png`
- Image displayed in terminal (if supported)

**Tips:**
- Be descriptive and specific in prompts
- Include art style, lighting, perspective
- Mention colors, composition, mood

---

### /vision

**Analyze image with vision model (OCR and content extraction)**

```bash
/vision <image_path> [optional task]
```

**What it does:**
- Analyzes image using vision-language model
- Extracts text (OCR)
- Describes visual content
- Converts to markdown format
- Optional custom analysis task

**When to use:**
- Extracting text from screenshots
- Analyzing charts and graphs
- Converting images to markdown
- Image content description

**Examples:**
```bash
/vision screenshot.png
/vision chart.png describe the trends shown
/vision diagram.jpg extract all labels and annotations
/vision receipt.png convert to structured data
```

**Default task:**
"Convert this image to markdown format, preserving all text, tables, charts, and structure. Use OCR to extract any text."

**Model used:** Vision-language model (qwen/qwen3-vl-4b)

**Supported formats:** PNG, JPG, JPEG, GIF, WebP

**Output:**
- Markdown-formatted text
- Tables preserved
- Structure maintained
- Text extracted and formatted

---

### /develop

**Multi-step code development workflow**

```bash
/develop <development request>
```

**What it does:**

**Phase 0: Pre-flight Checks**
- Verifies git repository exists (required for safety)
- Warns if uncommitted changes present
- Asks for confirmation to proceed

**Phase 1: Codebase Exploration**
- Analyzes project structure and file types
- Detects project type (Node.js, Python, Go, Rust)
- Identifies framework (Express, Flask, Next.js, etc.)
- Reads configuration files (package.json, requirements.txt, etc.)
- Maps dependencies and entry points

**Phase 2: Planning**
- Uses reasoning model to create detailed plan
- Identifies files to create/modify
- Specifies dependencies to add
- Orders tasks logically
- Includes testing recommendations

**Phase 3: User Approval**
- Displays plan with rich formatting
- Options:
  - **[A]pprove** - Proceed to execution
  - **[M]odify** - Provide new prompt, restart planning
  - **[C]ancel** - Abort workflow

**Phase 4: Code Execution**
- Uses Codestral to generate code
- Creates new files or edits existing files
- Tracks all modifications
- Shows progress for each task

**Phase 5: Linting & Validation**
- Auto-detects linters (eslint, prettier, ruff, pylint, etc.)
- Runs linting on all modified files
- Auto-fixes errors when possible
- Reports final status

**Phase 6: Dependency Installation**
- Auto-runs package manager install commands
- npm install (Node.js)
- pip install (Python)
- go mod download (Go)
- cargo build (Rust)

**When to use:**
- Adding new features to existing codebase
- Refactoring code across multiple files
- Implementing API endpoints
- Database migrations
- Any multi-file code changes

**Requirements:**
- **Git repository** (workflow will abort if not present)
- Codebase in working directory
- Recommended: Clean git state (no uncommitted changes)

**Examples:**
```bash
/develop add a REST API endpoint for user authentication
/develop refactor database connection to use connection pooling
/develop implement rate limiting middleware for Express
/develop add unit tests for the user service
```

**Safety features:**
- Git required (easy rollback with `git checkout`)
- User approval before any file changes
- Only operates within working directory
- Never deletes files (only creates/edits)
- Modification loop if plan needs adjustment
- Warns before modifying sensitive files

**Configuration:**
```python
DEVELOP = {
    "explorer_model": "orchestrator",  # Fast exploration
    "planner_model": "reasoning",      # High-quality planning
    "coder_model": "codestral",        # Specialized code generation
    "max_files_explore": 1000,         # Warn on large codebases
    "enable_linting": True,
    "auto_fix_lint": True,
    "auto_install_deps": True,
    "require_git": True,
}
```

**Tips:**
- Be specific in your request
- Mention the framework/technology if applicable
- Check `git status` before running
- Review the plan carefully before approving
- Use "Modify" to refine the plan if needed

**Example workflow:**
```
> /develop add logging to all API endpoints

Pre-flight checks...
  ✓ Git repository detected
  ⚠ You have uncommitted changes
    Recommendation: Commit or stash changes first
    Proceed anyway? (y/n): y

Phase 1: Codebase Exploration
🔍 Exploring codebase in /Users/user/project...
  ✓ Detected nodejs project
  ✓ Analyzed 42 files across 8 directories
  ✓ Read 5 configuration files

Phase 2: Planning
📋 Creating implementation plan...
  ✓ Plan created with 5 tasks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPLEMENTATION PLAN

Overview:
Add logging middleware and integrate with existing Express routes

Changes Required:
1. Create new file: src/middleware/logger.js
   - Winston logging middleware
   - Request/response logging
   - Error tracking

2. Modify: src/app.js
   - Import and mount logger middleware
   - Add logging configuration

[... more tasks ...]

[A]pprove  [M]odify  [C]ancel: a

Phase 4: Code Execution
⚙️  Executing plan...
  ✓ Created src/middleware/logger.js (58 lines)
  ✓ Modified src/app.js
  ✓ Created src/config/logging.js (22 lines)

Phase 5: Linting
🔧 Validating code quality...
  ✓ src/middleware/logger.js - Passed
  ✓ src/app.js - Passed (auto-fixed formatting)
  ✓ src/config/logging.js - Passed

Installing dependencies...
  ✓ Dependencies installed (npm install)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ DEVELOPMENT COMPLETE

Summary:
- Files created: 2
- Files modified: 1
- Lint status: ✓ All passed

Next steps:
1. Test the changes
2. Review and commit:
   git status
   git diff
   git add .
   git commit -m "Add logging to API endpoints"

Ready for testing!
```

---

## System Commands

Commands for configuration, history, and session management.

### /models

**Interactive model configuration**

```bash
/models
```

**What it does:**
- Shows current model configuration
- Allows changing orchestrator model
- Configure Codestral endpoint (local or HuggingFace)
- Add/edit HuggingFace inference endpoints
- Update HuggingFace API token
- Save changes to configuration

**Options:**
1. Change orchestrator model (4B recommended for RAM efficiency)
2. Configure Codestral endpoint (local vs HF)
3. Add HuggingFace endpoint
4. Update HF token
5. Save and exit

**Example:**
```
> /models

Zorora Model Configuration
────────────────────────────────────────

Current Configuration:
  Orchestrator: qwen/qwen3-vl-4b (local)
  Codestral:    qwen-coder-32b (HuggingFace)
  Reasoning:    qwen/qwen3-4b-thinking-2507 (local)

Options:
  1. Change orchestrator model
  2. Configure Codestral endpoint
  3. Add HuggingFace endpoint
  4. Update HF token
  5. Save and exit

Select option: 2
```

**Recommendations:**
- **Orchestrator:** 4B local model (RAM efficiency)
- **Codestral:** 32B HF endpoint (code quality) or 4B local (speed)
- **Reasoning:** 32B model for better planning and synthesis

---

### /config

**Show routing configuration**

```bash
/config
```

**What it does:**
- Displays current routing patterns
- Shows configured models and endpoints
- Lists active workflows
- Shows tool configuration

**Interactive configuration editor:**
- Toggle settings on/off
- Adjust confidence thresholds
- Enable/disable features
- Save changes

**Configuration options:**
- USE_JSON_ROUTING
- USE_HEURISTIC_ROUTER
- ENABLE_CONFIDENCE_FALLBACK
- CONFIDENCE_THRESHOLD_HIGH
- CONFIDENCE_THRESHOLD_LOW

---

### /history

**Browse saved conversation sessions**

```bash
/history
```

**What it does:**
- Lists all saved conversation sessions
- Shows session ID, message count, start time
- Allows selecting session to resume

**Output:**
```
Conversation History
────────────────────────────────────────
1. session_2025-12-21_07-36-28
   Messages: 12
   Started: 2025-12-21 07:36:28

2. session_2025-12-20_15-30-15
   Messages: 24
   Started: 2025-12-20 15:30:15

[... more sessions ...]
```

**Storage location:** `.zorora/conversations/`

**Auto-save:** Conversations automatically saved after each turn

---

### /resume

**Resume a previous conversation session**

```bash
/resume <session_id>
```

**What it does:**
- Loads conversation from specified session
- Restores full context
- Continues from where you left off

**Example:**
```bash
/resume session_2025-12-21_07-36-28
```

**Session IDs:** Find using `/history` command

---

### /save

**Save last specialist output to file**

```bash
/save <filename>
```

**What it does:**
- Saves most recent tool output to file
- Works with code generation, research, etc.
- Creates file in current directory

**Example:**
```bash
> /code write a CSV parser
[Code generated...]
> /save csv_parser.py
Saved to: csv_parser.py
```

---

### /clear

**Clear conversation context**

```bash
/clear
```

**What it does:**
- Resets conversation to fresh state
- Clears message history
- Maintains configuration and settings

**When to use:**
- Starting a new topic
- Clearing cluttered context
- Resetting after errors

---

### /visualize

**Show context usage statistics**

```bash
/visualize
```

**What it does:**
- Displays current message count
- Shows context limit
- Visualizes usage with progress bar
- Shows summarization status

**Example output:**
```
Context Usage Statistics
────────────────────────────────────────
Messages:     12 / 50 (24%)
Status:       [████░░░░░░░░░░░░░░░░] 24%
Summarized:   No
Recent kept:  All messages
```

---

### /help

**Show available commands**

```bash
/help
```

**What it does:**
- Lists all workflow commands with examples
- Lists all system commands
- Shows usage notes

**Categories:**
- Workflow Commands
- System Commands
- Additional notes

---

## Natural Language Queries

In addition to slash commands, Zorora automatically routes natural language queries.

### Auto-routing patterns

**Research (newsroom + web + synthesis):**
- Questions: "What are...", "How does...", "Why is..."
- Multi-source: "Based on newsroom and web..."
- Current events: "Latest...", "Recent...", "2025..."

**Code generation:**
- "Write a function..."
- "Generate code for..."
- "Create a script..."

**File operations:**
- "List files in current directory"
- "Save this research"
- "Load my notes on..."

### Forcing workflows

If auto-routing doesn't work as expected, use slash commands to force specific behavior:
- Use `/search` instead of "Search for..."
- Use `/code` instead of "Write code for..."
- Use `/ask` for follow-ups without triggering search

---

## Tips and Best Practices

### General
- Use slash commands when auto-routing is ambiguous
- Check `/history` to find previous sessions
- Use `/clear` when switching topics
- Configure models once with `/models`

### Research
- Use `/search` for time-sensitive queries
- Save important findings with approval or `/save`
- Load previous research to build on findings
- Check source URLs for verification

### Code Development
- Use `/develop` for multi-file changes
- Use `/code` for quick snippets
- Always review generated code before running
- Test generated code in isolated environment

### Safety
- `/develop` requires git repository
- Review plans before approving
- Check `git diff` after `/develop` completes
- Keep backups of important work

---

**Last Updated:** 2025-12-21
**See also:** [README.md](README.md) for architecture and setup
