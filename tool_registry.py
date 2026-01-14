"""
DEPRECATED: This file is kept for backward compatibility only.
Use 'from tools.registry import ...' instead.

This shim will be removed in a future release.
"""

import warnings

warnings.warn(
    "Importing from tool_registry is deprecated. "
    "Use 'from tools.registry import ...' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from tools.registry
from tools.registry import (
    TOOL_FUNCTIONS,
    TOOL_ALIASES,
    TOOLS_DEFINITION,
    SPECIALIST_TOOLS,
    MIGRATED_TOOLS,
    ToolRegistry,
    # Research tools
    academic_search,
    web_search,
    get_newsroom_headlines,
    # File operations
    read_file,
    write_file,
    edit_file,
    make_directory,
    list_files,
    get_working_directory,
    # Shell operations
    run_shell,
    apply_patch,
    # Specialist tools
    use_coding_agent,
    use_reasoning_model,
    use_search_model,
    use_intent_detector,
    use_energy_analyst,
    # Image tools
    analyze_image,
    generate_image,
    web_image_search,
)

__all__ = [
    'TOOL_FUNCTIONS',
    'TOOL_ALIASES',
    'TOOLS_DEFINITION',
    'SPECIALIST_TOOLS',
    'MIGRATED_TOOLS',
    'ToolRegistry',
    # Research tools
    'academic_search',
    'web_search',
    'get_newsroom_headlines',
    # File operations
    'read_file',
    'write_file',
    'edit_file',
    'make_directory',
    'list_files',
    'get_working_directory',
    # Shell operations
    'run_shell',
    'apply_patch',
    # Specialist tools
    'use_coding_agent',
    'use_reasoning_model',
    'use_search_model',
    'use_intent_detector',
    'use_energy_analyst',
    # Image tools
    'analyze_image',
    'generate_image',
    'web_image_search',
]
