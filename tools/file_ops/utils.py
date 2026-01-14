"""
Path resolution and validation utilities for file operations.
"""

from pathlib import Path


def _resolve_path(path: str, working_directory=None):
    """
    Resolve a path against the working directory.

    Args:
        path: Path to resolve (can be relative, absolute, or use ~)
        working_directory: Current working directory (Path object or None)

    Returns:
        Resolved Path object
    """
    # Expand ~ to home directory
    path_obj = Path(path).expanduser()

    # If absolute, use as-is
    if path_obj.is_absolute():
        return path_obj

    # If relative and working_directory provided, resolve against it
    if working_directory is not None:
        return (working_directory / path_obj).resolve()

    # Otherwise use current working directory
    return path_obj.resolve()


def _validate_path(path: str) -> tuple[bool, str]:
    """
    Validate file path for security.

    Returns:
        (is_valid, error_message)
    """
    try:
        file_path = Path(path).resolve()
        home_dir = Path.home().resolve()

        # Prevent path traversal outside home directory
        # (More permissive than CWD to allow stateful navigation)
        if not str(file_path).startswith(str(home_dir)):
            return False, f"Error: Path must be within home directory ({home_dir})"

        return True, ""
    except Exception as e:
        return False, f"Error: Invalid path '{path}': {e}"


def _find_similar_substring(content: str, target: str, context_chars: int = 100) -> str:
    """
    Find similar substring in content (handles whitespace differences).

    Returns a snippet of similar text if found, empty string otherwise.
    """
    # Normalize whitespace for comparison
    normalized_target = ' '.join(target.split())
    normalized_content = ' '.join(content.split())

    if len(normalized_target) < 10:
        return ""  # Too short to meaningfully match

    if normalized_target in normalized_content:
        # Find approximate location in original content
        # Search for first significant word from target
        words = [w for w in target.split() if len(w) > 3]
        if words:
            first_word = words[0]
            idx = content.find(first_word)
            if idx >= 0:
                start = max(0, idx - context_chars)
                end = min(len(content), idx + len(target) + context_chars)
                return content[start:end]
    return ""


def _find_line_numbers(content: str, substring: str) -> str:
    """
    Find line numbers where substring appears.

    Returns comma-separated list of line numbers (truncated if >10).
    """
    lines = content.splitlines()
    locations = []

    # For multi-line substrings, find which lines contain the start
    sub_first_line = substring.split('\n')[0] if '\n' in substring else substring

    for i, line in enumerate(lines, 1):
        if sub_first_line in line:
            locations.append(str(i))
        elif substring in line:
            locations.append(str(i))

    if len(locations) > 10:
        return ", ".join(locations[:10]) + f"... ({len(locations)} total)"
    return ", ".join(locations) if locations else "unknown"
