"""
Shell operations tools - modular implementation.

Provides secure shell command execution and patch application.
"""

from tools.shell.run import run_shell
from tools.shell.patch import apply_patch

__all__ = [
    "run_shell",
    "apply_patch",
]
