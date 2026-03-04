"""Thin yfinance client — matches fred_client.py fetch_observations signature."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import config

logger = logging.getLogger(__name__)


def fetch_observations(
    ticker: str,
    start_date: Optional[str] = None,
) -> List[Tuple[str, float]]:
    """Fetch daily close prices from Yahoo Finance via yfinance.

    Returns list of (date_str, value) tuples — same format as fred_client.
    """
    timeout = config.YFINANCE.get("timeout", 30)

    try:
        import yfinance as yf

        kwargs = {"tickers": ticker, "progress": False, "timeout": timeout}
        if start_date:
            kwargs["start"] = start_date
        else:
            kwargs["period"] = "max"

        df = yf.download(**kwargs)
    except Exception as exc:
        logger.error("yfinance download failed for %s: %s", ticker, exc)
        return []

    if df is None or df.empty:
        logger.warning("No data returned for %s", ticker)
        return []

    # yfinance returns MultiIndex columns when downloading single ticker
    # in newer versions: ('Close', 'TICKER'). Flatten to just Close.
    if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
        if "Close" in df.columns.get_level_values(0):
            close = df["Close"]
            if hasattr(close, "columns"):
                close = close.iloc[:, 0]
        else:
            close = df.iloc[:, 0]
    elif "Close" in df.columns:
        close = df["Close"]
    else:
        close = df.iloc[:, 0]

    observations: List[Tuple[str, float]] = []
    for dt, val in close.items():
        if val is not None:
            try:
                fval = float(val)
                if fval == fval:  # NaN check
                    observations.append((str(dt.date()), fval))
            except (ValueError, TypeError, AttributeError):
                continue

    logger.info("Fetched %d observations for %s", len(observations), ticker)
    return observations
