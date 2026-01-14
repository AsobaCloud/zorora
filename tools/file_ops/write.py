"""
File writing tool.
"""

from pathlib import Path
from tools.file_ops.utils import _resolve_path, _validate_path


def write_file(path: str, content: str, working_directory=None) -> str:
    """
    Write content to a file (creates or overwrites).

    Args:
        path: Path to the file to write
        content: Content to write to the file
        working_directory: Optional working directory for path resolution

    Returns:
        Success or error message
    """
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    # Validate path security
    is_valid, error = _validate_path(str(resolved_path))
    if not is_valid:
        return error

    try:
        Path(resolved_path).write_text(content)
        return f"OK: Written {len(content)} characters to '{resolved_path}'"
    except Exception as e:
        return f"Error writing file: {e}"
