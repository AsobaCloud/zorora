"""Sandboxed code execution for data analysis.

Executes user-provided Python code with a curated set of globals
(df, pd, np, scipy, plt) and returns structured JSON results.
"""

import json
import os
import re
import tempfile
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tools.data_analysis import session

logger = logging.getLogger(__name__)

# Blocked imports — modules that should never be accessible
_BLOCKED_MODULES = frozenset({
    "os", "sys", "subprocess", "shutil", "signal", "socket",
    "http", "urllib", "ftplib", "smtplib", "ctypes", "multiprocessing",
    "threading", "importlib", "pathlib", "io", "builtins",
    "pickle", "shelve", "marshal", "code", "codeop", "compileall",
})

# Pattern to detect dangerous import statements
_IMPORT_PATTERN = re.compile(
    r'(?:^|\n)\s*(?:import|from)\s+(' + '|'.join(_BLOCKED_MODULES) + r')\b',
    re.MULTILINE,
)

# Blocked builtins
_BLOCKED_BUILTINS = {"open", "exec", "eval", "compile", "__import__",
                     "globals", "locals", "breakpoint", "exit", "quit",
                     "input", "help", "memoryview", "classmethod", "staticmethod",
                     "super", "delattr", "setattr", "getattr", "vars", "dir"}

# Safe builtins allowlist
_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
    "bytearray": bytearray, "bytes": bytes, "callable": callable,
    "chr": chr, "complex": complex, "dict": dict, "divmod": divmod,
    "enumerate": enumerate, "filter": filter, "float": float,
    "format": format, "frozenset": frozenset, "hash": hash, "hex": hex,
    "int": int, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list, "map": map, "max": max,
    "min": min, "next": next, "object": object, "oct": oct, "ord": ord,
    "pow": pow, "print": print, "property": property, "range": range,
    "repr": repr, "reversed": reversed, "round": round, "set": set,
    "slice": slice, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
}


def execute_analysis(code: str, session_id: str = "", plot_dir: str = "") -> str:
    """Execute analysis code in a sandboxed environment.

    Args:
        code: Python code to execute. Should set ``result`` variable for output.
        session_id: Session to pull DataFrame from.
        plot_dir: Directory for plot output. Defaults to tempdir.

    Returns:
        JSON string ``{result, type, plot_generated, plot_path}`` on success,
        or ``"Error: <description>"`` on failure.
    """
    # Validate code
    if not code or not code.strip():
        return "Error: Empty code"

    # Check for blocked imports
    import_match = _IMPORT_PATTERN.search(code)
    if import_match:
        return f"Error: Import of '{import_match.group(1)}' is not allowed"

    # Check for blocked builtins used directly
    for blocked in ("__import__",):
        if blocked in code:
            return f"Error: '{blocked}' is not allowed"

    # Get DataFrame from session
    df = session.get_df(session_id)
    if df is None:
        return "Error: No dataset loaded. Use /load <path> first."

    # Set up plot directory
    if not plot_dir:
        plot_dir = tempfile.mkdtemp(prefix="zorora_plots_")

    plot_sentinel = os.path.join(plot_dir, "__zorora_plot__.png")

    # Build safe globals
    safe_globals = {
        "__builtins__": _SAFE_BUILTINS,
        "df": df,
        "pd": pd,
        "np": np,
        "plt": plt,
        "result": None,
    }

    # Allow scipy imports via a safe import mechanism
    def _safe_import(name, *args, **kwargs):
        if name == "scipy" or name.startswith("scipy."):
            import scipy
            if name == "scipy":
                return scipy
            # Handle submodule imports like "scipy.stats"
            parts = name.split(".")
            mod = scipy
            for part in parts[1:]:
                mod = getattr(mod, part)
            return mod
        raise ImportError(f"Import of '{name}' is not allowed")

    safe_globals["__builtins__"]["__import__"] = _safe_import

    # Change to plot dir so relative savefig paths work
    original_cwd = os.getcwd()

    try:
        os.chdir(plot_dir)
        plt.close("all")

        # Compile first to catch syntax errors
        compiled = compile(code, "<analysis>", "exec")
        exec(compiled, safe_globals)

        # Extract result
        raw_result = safe_globals.get("result")
        result_type, result_str = _format_result(raw_result)

        # Check for plot
        plot_generated = os.path.exists(plot_sentinel)
        plot_path = plot_sentinel if plot_generated else None

        return json.dumps({
            "result": result_str,
            "type": result_type,
            "plot_generated": plot_generated,
            "plot_path": plot_path,
        })

    except SyntaxError as e:
        return f"Error: Syntax error — {e}"
    except ImportError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {type(e).__name__} — {e}"
    finally:
        os.chdir(original_cwd)


def _format_result(raw) -> tuple:
    """Format a raw result into (type_name, string_representation)."""
    if raw is None:
        return "none", "None"

    if isinstance(raw, pd.DataFrame):
        return "dataframe", raw.to_string()

    if isinstance(raw, pd.Series):
        return "series", raw.to_string()

    if isinstance(raw, (int, float, np.integer, np.floating)):
        return "scalar", str(raw)

    if isinstance(raw, str):
        return "string", raw

    if isinstance(raw, (list, dict, tuple)):
        return "collection", str(raw)

    return "other", str(raw)
