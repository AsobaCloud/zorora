"""
Directory operations tools.
"""

from pathlib import Path
from tools.file_ops.utils import _resolve_path, _validate_path


def make_directory(path: str, working_directory=None) -> str:
    """
    Create a new directory (including parent directories if needed).

    Args:
        path: Path for the new directory
        working_directory: Optional working directory for path resolution

    Returns:
        Success or error message
    """
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    try:
        dir_path = Path(resolved_path).resolve()
        home_dir = Path.home().resolve()

        # Security: Only allow creating directories within home directory
        if not str(dir_path).startswith(str(home_dir)):
            return f"Error: Can only create directories within home directory ({home_dir})"

        if dir_path.exists():
            if dir_path.is_dir():
                return f"OK: Directory '{resolved_path}' already exists"
            else:
                return f"Error: '{resolved_path}' exists but is not a directory"

        dir_path.mkdir(parents=True, exist_ok=True)
        return f"OK: Created directory '{resolved_path}'"
    except PermissionError:
        return f"Error: Permission denied to create directory '{resolved_path}'"
    except Exception as e:
        return f"Error creating directory: {e}"


def list_files(path: str = ".", working_directory=None) -> str:
    """
    List files and directories in a path.

    Args:
        path: Path to list (default: current directory)
        working_directory: Optional working directory for path resolution

    Returns:
        Newline-separated list of items or error message
    """
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    # Validate path security
    is_valid, error = _validate_path(str(resolved_path))
    if not is_valid:
        return error

    try:
        dir_path = Path(resolved_path)
        if not dir_path.exists():
            return f"Error: Path '{path}' does not exist."
        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory."
        items = [p.name for p in dir_path.iterdir()]
        return "\n".join(sorted(items)) if items else "(empty directory)"
    except Exception as e:
        return f"Error listing files: {e}"


def get_working_directory(working_directory=None) -> str:
    """
    Get the current working directory.

    Args:
        working_directory: Optional working directory (if provided, returns this)

    Returns:
        Current working directory path
    """
    if working_directory is not None:
        return f"Current working directory: {working_directory}"
    else:
        return f"Current working directory: {Path.cwd()}"
