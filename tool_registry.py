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
    ToolRegistry
)

__all__ = [
    'TOOL_FUNCTIONS',
    'TOOL_ALIASES',
    'TOOLS_DEFINITION',
    'SPECIALIST_TOOLS',
    'ToolRegistry'
]
