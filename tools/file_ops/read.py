"""
File reading tool with line number support.
"""

from pathlib import Path
from tools.file_ops.utils import _resolve_path, _validate_path


def read_file(path: str, working_directory=None, show_line_numbers: bool = True) -> str:
    """
    Read contents of a file with line numbers for precise editing.

    Args:
        path: Path to the file to read
        working_directory: Optional working directory for path resolution
        show_line_numbers: If True, prefix each line with line number (default: True)

    Returns:
        File contents with line numbers (format: "   123\t<content>")
    """
    # Resolve path against working directory if provided
    resolved_path = _resolve_path(path, working_directory)

    # Validate path security
    is_valid, error = _validate_path(str(resolved_path))
    if not is_valid:
        return error

    file_path = Path(resolved_path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    # Check file size limit (10MB)
    if file_path.stat().st_size > 10_000_000:
        return f"Error: File '{path}' too large (>10MB)"

    try:
        content = file_path.read_text()

        if show_line_numbers:
            lines = content.splitlines()
            # Format like cat -n: right-aligned line number + tab + content
            numbered = []
            for i, line in enumerate(lines, 1):
                numbered.append(f"{i:6d}\t{line}")
            return "\n".join(numbered)
        else:
            return content
    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
    except Exception as e:
        return f"Error reading file: {e}"
