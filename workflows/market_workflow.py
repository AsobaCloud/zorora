"""Market data workflow — fetch, cache, chart, and analyze market series."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from tools.market import fred_client, yfinance_client, worldbank_client
from tools.market.series import (
    GROUPS,
    SERIES_CATALOG,
    get_all_series_ids,
    get_series_by_group,
)
from tools.market.store import MarketDataStore
from tools.market.context import build_market_context

logger = logging.getLogger(__name__)


class MarketWorkflow:
    """Orchestrates market data fetch, charting, and LLM analysis."""

    def __init__(self, store: Optional[MarketDataStore] = None):
        self.store = store or MarketDataStore()
        self.stale_hours = config.MARKET_DATA.get("stale_threshold_hours", 24)
        self.chart_dir = Path(config.MARKET_DATA.get("chart_output_dir", "plots")) / "market"
        self.chart_dpi = config.MARKET_DATA.get("chart_dpi", 150)
        self.chart_style = config.MARKET_DATA.get("chart_style", "seaborn-v0_8-darkgrid")

    # ------------------------------------------------------------------
    # Data fetch
    # ------------------------------------------------------------------

    def update_all(self, force: bool = False) -> int:
        """Fetch/update all series. Returns number of series updated."""
        count = 0
        for sid in get_all_series_ids():
            if self._update_series(sid, force):
                count += 1
        return count

    def update_group(self, group: str, force: bool = False) -> int:
        """Fetch/update series in one group."""
        count = 0
        for s in get_series_by_group(group):
            if self._update_series(s.series_id, force):
                count += 1
        return count

    def _update_series(self, series_id: str, force: bool = False) -> bool:
        """Fetch a single series (incremental unless force). Returns True if fetched."""
        series = SERIES_CATALOG.get(series_id)
        provider = series.provider if series else "fred"

        # Check provider-specific enabled flag
        if provider == "fred" and not config.FRED.get("enabled", True):
            return False
        if provider == "yfinance" and not config.YFINANCE.get("enabled", True):
            return False
        wb_config = getattr(config, "WORLD_BANK_INDICATORS", {})
        if provider == "worldbank" and not wb_config.get("enabled", True):
            return False
        sapp_config = getattr(config, "SAPP", {})
        if provider == "sapp" and not sapp_config.get("enabled", True):
            return False
        eskom_config = getattr(config, "ESKOM", {})
        if provider == "eskom" and not eskom_config.get("enabled", True):
            return False

        staleness = self.store.get_staleness(series_id, provider=provider)
        if not force and staleness is not None and staleness < self.stale_hours:
            return False

        # Incremental: start from last stored date
        start_date = None
        if not force:
            last = self.store.get_last_observation_date(series_id, provider=provider)
            if last:
                start_date = last

        # Dispatch to correct client
        if provider == "yfinance":
            obs = yfinance_client.fetch_observations(series_id, start_date=start_date)
        elif provider == "worldbank":
            start_year = int(start_date[:4]) if start_date else None
            obs = worldbank_client.fetch_observations(series_id, start_year=start_year)
        elif provider == "sapp":
            from tools.market import sapp_client
            # Derive node and currency from series_id: sapp_dam_rsan_usd
            parts = series_id.split("_")
            node = parts[2] if len(parts) >= 4 else ""
            currency = parts[3] if len(parts) >= 4 else "usd"
            file_name = sapp_config.get("dam_files", {}).get(node)
            if not file_name:
                return False
            file_path = str(Path(sapp_config.get("data_dir", "data")) / file_name)
            obs = sapp_client.fetch_observations(file_path, currency=currency)
        elif provider == "eskom":
            from tools.market import eskom_client
            data_dir = eskom_config.get("data_dir", "data")
            # Route to correct parser based on series_id prefix
            if series_id.startswith("eskom_re_"):
                col_key = series_id[len("eskom_re_"):]
                file_path = str(Path(data_dir) / eskom_config.get("generation_file", "Hourly_Generation.csv"))
                all_obs = eskom_client.fetch_generation_observations(file_path)
                obs = all_obs.get(col_key, [])
            elif series_id in ("eskom_residual_forecast", "eskom_rsa_contracted_forecast",
                               "eskom_residual_demand", "eskom_rsa_contracted_demand"):
                col_key = series_id[len("eskom_"):]
                file_path = str(Path(data_dir) / eskom_config.get("demand_file", "System_hourly_actual_and_forecasted_demand.csv"))
                all_obs = eskom_client.fetch_demand_observations(file_path)
                obs = all_obs.get(col_key, [])
            else:
                col_key = series_id[len("eskom_"):]
                file_path = str(Path(data_dir) / eskom_config.get("station_buildup_file", "Station_Build_Up.csv"))
                all_obs = eskom_client.fetch_station_buildup_observations(file_path)
                obs = all_obs.get(col_key, [])
        else:
            obs = fred_client.fetch_observations(series_id, observation_start=start_date)

        if obs:
            self.store.upsert_observations(series_id, obs, provider=provider)
        return True

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    def generate_dashboard(self, lookback_days: int = 365) -> List[str]:
        """Generate one chart per group. Returns list of PNG paths."""
        paths = []
        for group_name in GROUPS:
            path = self.generate_group_chart(group_name, lookback_days)
            if path:
                paths.append(path)
        return paths

    def generate_group_chart(self, group: str, lookback_days: int = 365) -> Optional[str]:
        """Generate a multi-line chart for one group."""
        series_list = get_series_by_group(group)
        if not series_list:
            return None

        sids = [s.series_id for s in series_list]
        title = f"{group.title()} — {lookback_days}d"
        return self.generate_single_chart(sids, lookback_days, title)

    def generate_single_chart(
        self, series_ids: List[str], lookback_days: int, title: str
    ) -> Optional[str]:
        """Generate a single chart for the given series IDs. Returns PNG path."""
        start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        df = self.store.get_multi_series_df(series_ids, start_date=start)
        if df.empty:
            return None

        self.chart_dir.mkdir(parents=True, exist_ok=True)

        try:
            plt.style.use(self.chart_style)
        except OSError:
            pass  # fall back to default

        fig, ax = plt.subplots(figsize=(12, 5))

        # If columns have different units, normalise to % change from start
        units = set()
        for sid in series_ids:
            s = SERIES_CATALOG.get(sid)
            if s:
                units.add(s.unit)

        if len(units) > 1:
            # Normalize to % change
            normed = df.apply(lambda col: (col / col.dropna().iloc[0] - 1) * 100 if not col.dropna().empty else col)
            normed.plot(ax=ax)
            ax.set_ylabel("% change from start")
        else:
            df.plot(ax=ax)
            ax.set_ylabel(next(iter(units)) if units else "value")

        ax.set_title(title)
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        slug = title.lower().replace(" ", "_").replace("—", "").replace("/", "_")[:40]
        out_path = str(self.chart_dir / f"{slug}.png")
        fig.savefig(out_path, dpi=self.chart_dpi)
        plt.close(fig)
        logger.info("Saved chart: %s", out_path)
        return out_path

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    def compute_summary(self) -> Dict[str, dict]:
        """Compute per-series stats: current, 30d/90d/1Y % change, 30d volatility."""
        summaries: Dict[str, dict] = {}
        for sid in get_all_series_ids():
            series = SERIES_CATALOG.get(sid)
            provider = series.provider if series else "fred"
            df = self.store.get_series_df(sid, provider=provider)
            if df.empty or len(df) < 2:
                continue
            current = df["value"].iloc[-1]
            info: dict = {"current": current}

            for days, key in [(30, "pct_30d"), (90, "pct_90d"), (365, "pct_1y")]:
                cutoff = datetime.now() - timedelta(days=days)
                subset = df[df.index >= pd.Timestamp(cutoff)]
                if not subset.empty and subset["value"].iloc[0] != 0:
                    info[key] = ((current - subset["value"].iloc[0]) / abs(subset["value"].iloc[0])) * 100
                else:
                    info[key] = None

            # 30-day annualised volatility on daily returns
            recent = df["value"].tail(30)
            if len(recent) >= 5:
                returns = recent.pct_change().dropna()
                if not returns.empty:
                    info["vol_30d"] = float(returns.std() * np.sqrt(252) * 100)
                else:
                    info["vol_30d"] = None
            else:
                info["vol_30d"] = None

            summaries[sid] = info
        return summaries

    # ------------------------------------------------------------------
    # Correlations
    # ------------------------------------------------------------------

    def compute_correlations(self, group: str, lookback_days: int = 90) -> Optional[pd.DataFrame]:
        """Compute return-based correlation matrix for a group."""
        series_list = get_series_by_group(group)
        if len(series_list) < 2:
            return None

        start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        sids = [s.series_id for s in series_list]
        df = self.store.get_multi_series_df(sids, start_date=start)
        if df.empty or len(df) < config.MARKET_DATA.get("correlation_min_observations", 30):
            return None

        returns = df.pct_change().dropna()
        if returns.empty:
            return None
        return returns.corr()

    # ------------------------------------------------------------------
    # LLM analysis
    # ------------------------------------------------------------------

    def generate_analysis(
        self,
        summaries: Dict[str, dict],
        correlations: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> str:
        """Call reasoning model for 400-600 word market analysis."""
        context = build_market_context(summaries, correlations, max_chars=3000)
        if not context:
            return self._deterministic_summary(summaries)

        prompt = f"""You are a senior macro analyst. Using the market data below (FRED + yfinance), write a
400-600 word market analysis covering:
1. Key commodity movements and drivers (including renewable metals: copper, silver, platinum, palladium, aluminum, iron ore, steel)
2. Yield curve shape and recent shifts
3. Notable cross-asset correlations and what they signal
4. Energy transition supply-chain signals (ETF proxies for lithium, uranium, rare earths — note these track miners, not spot)
5. Risk factors and emerging-market implications (especially ZAR)

{context}

Write in clear, professional prose. Use specific numbers from the data. No bullet points."""

        try:
            from tools.registry import TOOL_FUNCTIONS
            reason = TOOL_FUNCTIONS.get("use_reasoning_model")
            if reason:
                result = reason(prompt)
                if result and not result.startswith("Error:"):
                    return result
        except Exception as exc:
            logger.error("LLM analysis failed: %s", exc)

        return self._deterministic_summary(summaries)

    def _deterministic_summary(self, summaries: Dict[str, dict]) -> str:
        """Fallback plain-text summary when LLM is unavailable."""
        lines = ["## Market Data Summary\n"]
        for group_name, series_list in GROUPS.items():
            lines.append(f"### {group_name.title()}")
            for s in series_list:
                info = summaries.get(s.series_id)
                if not info:
                    continue
                cur = info.get("current")
                if cur is None:
                    continue
                parts = [f"**{s.label}**: {cur:.2f} {s.unit}"]
                for period, key in [("30d", "pct_30d"), ("90d", "pct_90d"), ("1Y", "pct_1y")]:
                    pct = info.get(key)
                    if pct is not None:
                        parts.append(f"{period}: {pct:+.1f}%")
                vol = info.get("vol_30d")
                if vol is not None:
                    parts.append(f"vol: {vol:.1f}%")
                lines.append("  " + " | ".join(parts))
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        subcommand: str = "dashboard",
        group: Optional[str] = None,
        lookback_days: int = 365,
        force_update: bool = False,
    ) -> Tuple[str, List[str]]:
        """Run full market workflow. Returns (analysis_text, chart_paths)."""
        # Phase 1: Update data
        if subcommand == "update":
            if group:
                n = self.update_group(group, force=force_update)
            else:
                n = self.update_all(force=force_update)
            return f"Updated {n} series.", []

        # Auto-update stale data
        if group:
            self.update_group(group)
        else:
            self.update_all()

        # Phase 2: Charts
        if group:
            chart_paths = []
            p = self.generate_group_chart(group, lookback_days)
            if p:
                chart_paths.append(p)
        else:
            chart_paths = self.generate_dashboard(lookback_days)

        # Phase 3: Summary + correlations
        summaries = self.compute_summary()
        corr_dict: Dict[str, pd.DataFrame] = {}
        for g in GROUPS:
            if group and g != group:
                continue
            c = self.compute_correlations(g)
            if c is not None:
                corr_dict[g] = c

        # Phase 4: LLM analysis
        analysis = self.generate_analysis(summaries, corr_dict if corr_dict else None)

        return analysis, chart_paths
