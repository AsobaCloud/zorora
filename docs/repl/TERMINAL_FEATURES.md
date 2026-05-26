# Terminal Features in Zorora REPL

## Overview

The Zorora REPL (Read-Eval-Print Loop) provides a rich terminal interface with modern features for productive interaction. This document covers the terminal-specific capabilities available in the REPL interface.

## Remote ML Commands

Execute ML model observation workflows directly from the Zorora terminal:

### Available Commands:
```
/ml-list-challengers <customer_id>     - List challenger models
/ml-show-metrics <model_id>            - Show model evaluation metrics
/ml-diff <challenger> <production>     - Compare models
/ml-promote <customer> <model> <reason> - Promote to production
/ml-rollback <customer> <reason>       - Rollback to previous
/ml-audit-log <customer_id>            - View audit history
```

### Features:
- **Model Lifecycle Management** - List challengers, compare models, promote/rollback
- **Audit Logging** - Track all model changes with full audit trail
- **Dual Authentication** - Support for Bearer token and AWS IAM authentication
- **End-to-End Validation** - Comprehensive validation script for Zorora ↔ Ona Platform connectivity

## Prompt Toolkit Integration

Modern terminal input with enhanced user experience:

### Features:
- **Application/Frame/Layout** - Sophisticated terminal UI framework
- **Visual Input Box** - Clear input area with borders and styling
- **Enhanced Keyboard Navigation** - Improved cursor handling and input feedback
- **Syntax Highlighting** - Code and command highlighting as you type
- **Multi-line Support** - Easy input of complex queries and commands

## Boxed Input UI

The REPL features a distinctive boxed input interface:

### Visual Elements:
- **Prompt Numbering** - Sequential turn counting ([1], [2], [3], etc.)
- **Mode Indicators** - Current operation mode display (⚙, 🔍, 📋, etc.)
- **Status Indicators** - Visual feedback for processing states
- **Execution Timing** - Per-command execution time display
- **Tool Visualization** - Hierarchical display of tool execution flow

### Example Interface:
```
[1] ⚙ > /deep What are the latest AI trends?
[Phase 1: Exploration]
🔍 Processing query...
[Phase 2: Synthesis]
🧠 Generating research synthesis...
[Phase 3: Output]
📊 Research complete! Found 15 sources.
```

## Interactive Model Configuration

Configure models and endpoints directly from the terminal:

### Model Selector:
Access via `/models` command to:
- View currently configured models
- Switch between available endpoints (local, HF, OpenAI, Anthropic)
- Configure API keys for remote providers
- Test connections to configured endpoints

### Configuration Persistence:
- Model preferences saved between sessions
- Secure handling of API credentials
- Automatic fallback to local LM Studio when remote endpoints unavailable

## Workflow-Specific Terminal Features

### Development Workflow (`/develop`):
- Multi-step code development with approval process
- Phase-by-phase execution with progress tracking
- Interactive planning with modify/approve/cancel options
- Automatic linting and validation after code generation
- Git integration for safe experimentation

### Code Workflow (`/code`):
- Direct file editing without planning phase
- Smart file detection from natural language prompts
- Retry loop with error context for self-correcting edits
- Line number precision for accurate file modifications
- Backup and rollback capabilities for safety

### Research Workflow (`/deep` / `/research`):
- Configurable research depth (quick/standard/comprehensive)
- Real-time progress tracking during source aggregation
- Source credibility scoring and cross-reference visualization
- Follow-up chat capabilities grounded in research sources
- Export options for research results

## Customization and Preferences

### UI Customization:
- Color scheme configuration (enable/disable colors)
- Prompt formatting preferences
- Information density controls
- Logging verbosity adjustment

### Productivity Features:
- Command history navigation (↑/↓ arrows)
- Reverse search (Ctrl+R) for previous commands
- Tab completion for commands and file paths
- Session persistence and resume capabilities
- Output saving to files for later reference

## Performance Characteristics

### Startup Time:
- Initialization: <2 seconds
- Model loading: Depends on endpoint configuration
- Ready state: Immediately responsive after startup

### Memory Usage:
- Base REPL: ~500MB
- With local 4B model: 4-6 GB RAM
- With remote HF endpoints: 2-3 GB RAM (offloads to remote)

### Responsiveness:
- Input latency: <50ms typical
- Command processing: Variable based on task complexity
- Background operations: Non-blocking with progress indicators

## Accessibility Features

### Navigation:
- Full keyboard navigation support
- Screen reader compatible output
- High contrast mode options
- Adjustable text scaling

### Error Handling:
- Clear error messages with actionable guidance
- Contextual help for failed operations
- Recovery suggestions for common issues
- Graceful degradation when features unavailable