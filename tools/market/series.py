"""Market series catalog for multi-provider data tracking."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class MarketSeries:
    series_id: str
    label: str
    unit: str
    frequency: str
    group: str
    provider: str = "fred"


# Backward-compat alias
FREDSeries = MarketSeries


SERIES_CATALOG: Dict[str, MarketSeries] = {
    # --- FRED series (provider="fred") ---
    # Commodities
    "DCOILWTICO": MarketSeries("DCOILWTICO", "WTI Crude Oil", "USD/bbl", "daily", "commodities"),
    "DCOILBRENTEU": MarketSeries("DCOILBRENTEU", "Brent Crude Oil", "USD/bbl", "daily", "commodities"),
    "GOLDAMGBD228NLBM": MarketSeries("GOLDAMGBD228NLBM", "Gold (London Fix)", "USD/oz", "daily", "commodities"),
    "DHHNGSP": MarketSeries("DHHNGSP", "Natural Gas (Henry Hub)", "USD/MMBtu", "daily", "commodities"),
    # US Treasuries
    "DGS2": MarketSeries("DGS2", "2-Year Treasury", "%", "daily", "treasuries"),
    "DGS5": MarketSeries("DGS5", "5-Year Treasury", "%", "daily", "treasuries"),
    "DGS10": MarketSeries("DGS10", "10-Year Treasury", "%", "daily", "treasuries"),
    "DGS30": MarketSeries("DGS30", "30-Year Treasury", "%", "daily", "treasuries"),
    "DTB3": MarketSeries("DTB3", "3-Month T-Bill", "%", "daily", "treasuries"),
    # FX Rates
    "DEXUSEU": MarketSeries("DEXUSEU", "USD/EUR", "USD per EUR", "daily", "fx"),
    "DEXUSUK": MarketSeries("DEXUSUK", "USD/GBP", "USD per GBP", "daily", "fx"),
    "DEXCHUS": MarketSeries("DEXCHUS", "USD/CNY", "CNY per USD", "daily", "fx"),
    "DEXSFAR": MarketSeries("DEXSFAR", "USD/ZAR", "ZAR per USD", "daily", "fx"),
    # Policy Rates
    "DFF": MarketSeries("DFF", "Effective Fed Funds Rate", "%", "daily", "rates"),
    # --- yfinance series (provider="yfinance") ---
    # Metals (daily commodity futures)
    "HG=F": MarketSeries("HG=F", "Copper", "USD/lb", "daily", "metals", "yfinance"),
    "SI=F": MarketSeries("SI=F", "Silver", "USD/oz", "daily", "metals", "yfinance"),
    "PL=F": MarketSeries("PL=F", "Platinum", "USD/oz", "daily", "metals", "yfinance"),
    "PA=F": MarketSeries("PA=F", "Palladium", "USD/oz", "daily", "metals", "yfinance"),
    "ALI=F": MarketSeries("ALI=F", "Aluminum", "USD/mt", "daily", "metals", "yfinance"),
    "TIO=F": MarketSeries("TIO=F", "Iron Ore", "USD/mt", "daily", "metals", "yfinance"),
    "HRC=F": MarketSeries("HRC=F", "Steel HRC", "USD/st", "daily", "metals", "yfinance"),
    # ETF Proxies (daily ETF prices — track miners, not spot)
    "LIT": MarketSeries("LIT", "Lithium Miners ETF", "USD", "daily", "etf_proxies", "yfinance"),
    "URA": MarketSeries("URA", "Uranium Miners ETF", "USD", "daily", "etf_proxies", "yfinance"),
    "REMX": MarketSeries("REMX", "Rare Earth ETF", "USD", "daily", "etf_proxies", "yfinance"),
}


def _build_groups() -> Dict[str, List[MarketSeries]]:
    groups: Dict[str, List[MarketSeries]] = defaultdict(list)
    for s in SERIES_CATALOG.values():
        groups[s.group].append(s)
    return dict(groups)


GROUPS: Dict[str, List[MarketSeries]] = _build_groups()


def get_series_by_group(group: str) -> List[MarketSeries]:
    """Return all series in a group, or empty list if unknown."""
    return GROUPS.get(group, [])


def get_all_series_ids() -> List[str]:
    """Return all tracked series IDs."""
    return list(SERIES_CATALOG.keys())


def get_series_by_provider(provider: str) -> List[MarketSeries]:
    """Return all series for a given provider."""
    return [s for s in SERIES_CATALOG.values() if s.provider == provider]


def get_all_providers() -> List[str]:
    """Return sorted list of unique provider names."""
    return sorted({s.provider for s in SERIES_CATALOG.values()})
