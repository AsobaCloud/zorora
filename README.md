# Zorora - Claude Code-like Local REPL

A deterministic, tool-gated REPL for code assistance using local LLM (LM Studio).

## Architecture

**Key Principle**: This is a **controlled tool-using REPL**, not an autonomous agent.

```
User Input
  ↓
Controller (classifies intent, enforces rules)
  ↓
LLM (executor - proposes tool or FINAL)
  ↓
Tools (execute if needed)
  ↓
LLM (produces FINAL response)
```

## Features

- **Mandatory Tool Gating**: Filesystem-dependent queries require tools
- **Single-Turn Tool Loop**: One tool call per user turn maximum
- **No Hallucination**: Controller prevents FINAL without evidence
- **Deterministic**: Predictable behavior, no agent loops
- **Fast**: No 60s stalls, immediate responses

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start LM Studio server on `http://localhost:1234`

3. Run:
```bash
python main.py
```

## Usage

```
> list files

FINAL:
This directory contains:
- config.py
- llm.py
- tools.py
- parser.py
- controller.py
- repl.py
- main.py
```

```
> read config.py

FINAL:
config.py contains configuration constants...
```

## Module Structure

- `config.py` - Configuration and system prompt
- `llm.py` - LM Studio API client
- `tools.py` - Tool implementations (read_file, write_file, list_files, run_shell, apply_patch)
- `parser.py` - Output parsing utilities
- `controller.py` - Intent classification and tool gating
- `repl.py` - REPL loop
- `main.py` - Entry point

## Tools

- `read_file(path)` - Read file contents
- `write_file(path, content)` - Write file
- `list_files(path)` - List directory contents
- `run_shell(command)` - Execute shell command (with safety checks)
- `apply_patch(path, unified_diff)` - Apply patch to file

## Configuration

Edit `config.py` to change:
- API endpoint
- Model name
- Timeouts
- System prompt
