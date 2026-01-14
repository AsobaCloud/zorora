"""
File operations tools - modular implementation.

Provides secure file read/write/edit operations with path validation.
"""

from tools.file_ops.utils import _resolve_path, _validate_path, _find_similar_substring, _find_line_numbers
from tools.file_ops.read import read_file
from tools.file_ops.write import write_file
from tools.file_ops.edit import edit_file
from tools.file_ops.directory import make_directory, list_files, get_working_directory

__all__ = [
    # Public tools
    "read_file",
    "write_file",
    "edit_file",
    "make_directory",
    "list_files",
    "get_working_directory",
    # Utilities (for internal use)
    "_resolve_path",
    "_validate_path",
    "_find_similar_substring",
    "_find_line_numbers",
]
