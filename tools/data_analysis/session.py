"""Session store for data analysis — holds active DataFrame and metadata.

Module-level dict keyed by session_id (default "").
"""

import pandas as pd
from typing import Optional, Dict, Any

_SESSION: Dict[str, Dict[str, Any]] = {}


def set_df(df: pd.DataFrame, session_id: str = "", **metadata) -> None:
    """Store a DataFrame and optional metadata in the session."""
    _SESSION[session_id] = {
        "df": df,
        **metadata,
    }


def get_df(session_id: str = "") -> Optional[pd.DataFrame]:
    """Retrieve the active DataFrame for a session, or None."""
    entry = _SESSION.get(session_id)
    if entry is None:
        return None
    return entry.get("df")


def get_session(session_id: str = "") -> Optional[Dict[str, Any]]:
    """Retrieve the full session dict (df + metadata)."""
    return _SESSION.get(session_id)


def clear(session_id: str = "") -> None:
    """Remove a session."""
    _SESSION.pop(session_id, None)


def clear_all() -> None:
    """Remove all sessions."""
    _SESSION.clear()
