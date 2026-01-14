"""
Unified diff patch application.
"""

from pathlib import Path


def apply_patch(path: str, unified_diff: str) -> str:
    """
    Apply a unified diff patch to a file.

    Args:
        path: Path to the file to patch
        unified_diff: Unified diff content to apply

    Returns:
        Success or error message
    """
    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    try:
        original_lines = file_path.read_text().splitlines(keepends=True)
        diff_lines = unified_diff.splitlines(keepends=True)
        patched_lines = list(original_lines)

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            if line.startswith("@@"):
                i += 1
                hunk_lines = []
                while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                    hunk_lines.append(diff_lines[i])
                    i += 1
                i -= 1

                for hunk_line in hunk_lines:
                    if hunk_line.startswith("+"):
                        patched_lines.append(hunk_line[1:])
                    elif hunk_line.startswith("-"):
                        target = hunk_line[1:]
                        if target in patched_lines:
                            patched_lines.remove(target)
            i += 1

        file_path.write_text("".join(patched_lines))
        return f"OK: Applied patch to '{path}'"
    except Exception as e:
        return f"Error applying patch: {e}"
