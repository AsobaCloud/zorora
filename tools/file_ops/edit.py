"""
File editing tool with exact string replacement.
"""

from pathlib import Path
from tools.file_ops.utils import _resolve_path, _validate_path, _find_similar_substring, _find_line_numbers


def edit_file(path: str, old_string: str, new_string: str,
              replace_all: bool = False, working_directory=None) -> str:
    """
    Edit a file by replacing exact string match.

    You MUST read the file first with read_file before editing.
    The old_string must match exactly including whitespace and indentation.

    Args:
        path: Path to the file to edit
        old_string: Exact string to find and replace (must be unique or use replace_all)
        new_string: String to replace with
        replace_all: If True, replace all occurrences (default: False)
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

    file_path = Path(resolved_path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    try:
        # Read current content
        content = file_path.read_text()

        # Check if old_string exists
        if old_string not in content:
            # Try to find similar text to help the user
            similar = _find_similar_substring(content, old_string)
            if similar:
                return f"Error: Exact string not found. Similar text found:\n---\n{similar[:400]}\n---\nMake sure whitespace and indentation match exactly. Use read_file to see current content."
            return "Error: String not found in file. Use read_file to see current content and copy the exact text."

        # Count occurrences
        occurrences = content.count(old_string)

        if occurrences > 1 and not replace_all:
            # Show line numbers where string appears
            locations = _find_line_numbers(content, old_string)
            return f"Error: String appears {occurrences} times at lines {locations}. Either:\n1. Include more surrounding context to make it unique, or\n2. Set replace_all=True to replace all occurrences"

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            file_path.write_text(new_content)
            return f"OK: Replaced {occurrences} occurrence(s) in '{resolved_path}'"
        else:
            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content)
            return f"OK: Replaced 1 occurrence in '{resolved_path}'"

    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file"
    except Exception as e:
        return f"Error editing file: {e}"
