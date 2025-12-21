# Workflows

## Overview

Zorora uses deterministic workflows with hardcoded pipelines. Each workflow executes a fixed sequence of steps without LLM-based planning or iteration.

## The Four Main Workflows

### 1. Research Workflow

**When triggered:** Queries that ask questions, mention sources, or request information

**What happens:**
1. Fetch newsroom headlines (if available)
2. Search the web (always)
3. Synthesize both sources with citations
4. Return comprehensive answer

**Examples:**
```
> Based on the newsroom as well as web search, what are the major AI trends in 2025?
> What's happening with battery storage in California?
> Tell me about recent developments in renewable energy policy
```

**Pipeline (hardcoded, no LLM planning):**
```
Query
  ↓
[Step 1/3] Fetch newsroom articles
  ↓
[Step 2/3] Web search (Brave/DuckDuckGo)
  ↓
[Step 3/3] Synthesize with citations
  ↓
Result (with [Newsroom] and [Web] tags)
```

**Force with:** `/search <query>`

### 2. Code Workflow

**When triggered:** Requests to write, generate, or create code

**What happens:**
1. Route to Codestral specialist model
2. Generate code with explanation
3. Return formatted code

**Examples:**
```
> Write a Python function to validate email addresses
> Create a script that generates interactive charts
> Generate a class for parsing CSV files
```

**Model:** Local or remote Codestral (configurable via `/models`)

**Force with:** `/code <prompt>`

### 3. File Operations Workflow

**When triggered:** Commands to save, load, list, or show research

**What happens:**
1. Execute file operation (save/load/list/delete)
2. Interact with `~/.zorora/research/` directory
3. Return confirmation or content

**Examples:**
```
> Save this as "california_battery_storage"
> Load my research on AI trends
> List all my saved research
> Show me what I saved about FERC Order 2222
```

**Storage format:**
```markdown
---
{
  "topic": "California Battery Storage",
  "timestamp": "2025-12-20T15:30:00",
  "query": "battery storage in California",
  "sources": ["Newsroom", "Web"]
}
---

[Your research content with citations...]
```

### 4. Simple Q&A Workflow

**When triggered:** Simple questions that don't need research or code

**What happens:**
1. Direct query to reasoning model
2. Single-turn response
3. No tool use

**Examples:**
```
> What is a virtual power plant?
> Explain how demand response works
> Define capacity market
```

**Force with:** `/ask <query>`

## Development Workflow (`/develop`)

Multi-step code development workflow that explores codebase, plans changes, gets user approval, executes changes, and validates with linting.

### Phases

#### Phase 1: Codebase Exploration

**Purpose:** Understand existing code structure and context

**Sub-agent:** `CodebaseExplorer`
- Walks directory tree (excludes: node_modules, .git, __pycache__, venv, etc.)
- Identifies file types and directory structure
- Reads and analyzes key files (package.json, requirements.txt, README, main entry points)
- Detects framework/language patterns
- Maps dependencies and imports
- Identifies existing patterns (API structure, data models, utility functions)

**Output:** Structured summary containing:
- Project type (Node.js, Python, etc.)
- Directory structure
- Key files and their purposes
- Existing patterns and conventions
- Dependencies and tech stack
- Entry points

**Model:** Orchestrator model (cost-effective for file reading/analysis)

#### Phase 2: Planning

**Purpose:** Create detailed implementation plan based on codebase context

**Sub-agent:** `CodePlanner`
- Analyzes request in context of existing codebase
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

**Model:** Reasoning model for better planning

#### Phase 3: User Review & Approval

**Purpose:** Get user confirmation before making changes

**UI Interaction:**
- Display formatted plan with rich formatting
- Show files to be created/modified
- List dependencies to add
- Wait for user approval (yes/no)
- Option to cancel

#### Phase 4: Execution

**Purpose:** Execute planned changes

**Sub-agent:** `CodeExecutor`
- Creates new files
- Modifies existing files
- Installs dependencies
- Runs linters
- Validates changes

**Model:** Codestral specialist model

#### Phase 5: Validation

**Purpose:** Lint and validate changes

**Tools:**
- Run project-specific linters (eslint, pylint, etc.)
- Check for syntax errors
- Validate file structure
- Option to rollback (git checkout) if needed

### Usage

```
/develop add REST API endpoint for user authentication
/develop refactor database connection to use pooling
```

**Requirements:**
- Must be run in a git repository
- Requires user approval before execution

## Image Workflows

### Image Generation (`/image`)

**What happens:**
1. Route to FLUX Schnell model
2. Generate image from text prompt
3. Save image to disk
4. Return image path

**Example:**
```
/image a futuristic solar farm at sunset
```

### Image Analysis (`/vision`)

**What happens:**
1. Load image from path
2. Route to vision model
3. Analyze image content
4. Return analysis

**Examples:**
```
/vision screenshot.png extract all text
/vision chart.png describe this chart
```

## Research Persistence

### Saving Research

**Automatic prompt after synthesis:**
```
[1] ⚙ > What are AI trends in 2025?
[Research synthesis with citations...]

Would you like to save this research? (yes/no)
> yes
Topic name: AI Trends 2025
Saved to: ~/.zorora/research/ai_trends_2025.md
```

**Manual save:**
```
[2] ⚙ > Save this as "ai_trends_2025"
Saved to: ~/.zorora/research/ai_trends_2025.md
```

### Loading Research

```
[3] ⚙ > Load my research on AI trends
[Displays content from ~/.zorora/research/ai_trends_2025.md]
```

### Listing Research

```
[4] ⚙ > List all my saved research

Saved Research (3 files):
─────────────────────────────────────────────────────────
1. AI Trends 2025
   Query: "AI trends in 2025"
   Saved: 2025-12-20 15:30:00
   File: ai_trends_2025.md

2. California Battery Storage
   Query: "battery storage in California"
   Saved: 2025-12-19 10:15:00
   File: california_battery_storage.md

3. FERC Order 2222
   Query: "FERC Order 2222 requirements"
   Saved: 2025-12-18 14:45:00
   File: ferc_order_2222.md
```

### Storage Location

All research is saved to `~/.zorora/research/` with:
- **Filename:** Slugified topic name (e.g., `ai_trends_2025.md`)
- **Format:** Markdown with JSON frontmatter
- **Metadata:** Topic, timestamp, original query, sources used
- **Content:** Synthesized findings with citations

## Workflow Routing

Workflows are triggered by:
1. **Slash commands** - Explicit workflow selection (`/search`, `/code`, `/develop`, etc.)
2. **Pattern matching** - Automatic routing based on query patterns
3. **Forced workflow** - Internal routing decisions

See [ARCHITECTURE.md](ARCHITECTURE.md) for details on routing logic.
