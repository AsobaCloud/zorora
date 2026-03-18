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
    "DEXSFUS": MarketSeries("DEXSFUS", "USD/ZAR", "ZAR per USD", "daily", "fx"),
    # Policy Rates
    "DFF": MarketSeries("DFF", "Effective Fed Funds Rate", "%", "daily", "rates"),
    # --- yfinance series (provider="yfinance") ---
    # Commodities
    "GC=F": MarketSeries("GC=F", "Gold Futures", "USD/oz", "daily", "commodities", "yfinance"),
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
    # --- World Bank Indicators (provider="worldbank", frequency="annual") ---
    "NY.GDP.MKTP.CD": MarketSeries("NY.GDP.MKTP.CD", "World GDP (current USD)", "USD", "annual", "development", "worldbank"),
    "NY.GDP.MKTP.KD.ZG": MarketSeries("NY.GDP.MKTP.KD.ZG", "World GDP Growth", "%", "annual", "development", "worldbank"),
    "FP.CPI.TOTL.ZG": MarketSeries("FP.CPI.TOTL.ZG", "World Inflation (CPI)", "%", "annual", "development", "worldbank"),
    "NE.TRD.GNFS.ZS": MarketSeries("NE.TRD.GNFS.ZS", "Trade (% of GDP)", "%", "annual", "development", "worldbank"),
    "BX.KLT.DINV.WD.GD.ZS": MarketSeries("BX.KLT.DINV.WD.GD.ZS", "FDI Inflows (% GDP)", "%", "annual", "development", "worldbank"),
    "SI.POV.DDAY": MarketSeries("SI.POV.DDAY", "Poverty ($2.15/day)", "%", "annual", "development", "worldbank"),
    # --- SAPP Day-Ahead Market (provider="sapp", frequency="hourly") ---
    "sapp_dam_rsan_usd": MarketSeries("sapp_dam_rsan_usd", "SAPP DAM RSA-North (USD)", "USD/MWh", "hourly", "sapp_prices", "sapp"),
    "sapp_dam_rsan_zar": MarketSeries("sapp_dam_rsan_zar", "SAPP DAM RSA-North (ZAR)", "ZAR/MWh", "hourly", "sapp_prices", "sapp"),
    "sapp_dam_rsas_usd": MarketSeries("sapp_dam_rsas_usd", "SAPP DAM RSA-South (USD)", "USD/MWh", "hourly", "sapp_prices", "sapp"),
    "sapp_dam_rsas_zar": MarketSeries("sapp_dam_rsas_zar", "SAPP DAM RSA-South (ZAR)", "ZAR/MWh", "hourly", "sapp_prices", "sapp"),
    "sapp_dam_zim_usd": MarketSeries("sapp_dam_zim_usd", "SAPP DAM Zimbabwe (USD)", "USD/MWh", "hourly", "sapp_prices", "sapp"),
    "sapp_dam_zim_zar": MarketSeries("sapp_dam_zim_zar", "SAPP DAM Zimbabwe (ZAR)", "ZAR/MWh", "hourly", "sapp_prices", "sapp"),
    # --- Eskom Demand (provider="eskom", frequency="hourly") ---
    "eskom_residual_forecast": MarketSeries("eskom_residual_forecast", "Eskom Residual Forecast", "MW", "hourly", "eskom_demand", "eskom"),
    "eskom_rsa_contracted_forecast": MarketSeries("eskom_rsa_contracted_forecast", "Eskom RSA Contracted Forecast", "MW", "hourly", "eskom_demand", "eskom"),
    "eskom_residual_demand": MarketSeries("eskom_residual_demand", "Eskom Residual Demand", "MW", "hourly", "eskom_demand", "eskom"),
    "eskom_rsa_contracted_demand": MarketSeries("eskom_rsa_contracted_demand", "Eskom RSA Contracted Demand", "MW", "hourly", "eskom_demand", "eskom"),
    # --- Eskom RE Generation (provider="eskom", frequency="hourly") ---
    "eskom_re_wind": MarketSeries("eskom_re_wind", "Eskom Wind Generation", "MW", "hourly", "eskom_re_generation", "eskom"),
    "eskom_re_pv": MarketSeries("eskom_re_pv", "Eskom PV Generation", "MW", "hourly", "eskom_re_generation", "eskom"),
    "eskom_re_csp": MarketSeries("eskom_re_csp", "Eskom CSP Generation", "MW", "hourly", "eskom_re_generation", "eskom"),
    "eskom_re_other": MarketSeries("eskom_re_other", "Eskom Other RE Generation", "MW", "hourly", "eskom_re_generation", "eskom"),
    # --- Eskom Station Build-Up (provider="eskom", frequency="hourly") ---
    "eskom_thermal_gen_excl_pumping_and_sco": MarketSeries("eskom_thermal_gen_excl_pumping_and_sco", "Eskom Thermal Gen (excl pumping/SCO)", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_eskom_ocgt_sco_pumping": MarketSeries("eskom_eskom_ocgt_sco_pumping", "Eskom OCGT SCO Pumping", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_eskom_gas_sco_pumping": MarketSeries("eskom_eskom_gas_sco_pumping", "Eskom Gas SCO Pumping", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_hydro_water_sco_pumping": MarketSeries("eskom_hydro_water_sco_pumping", "Eskom Hydro Water SCO Pumping", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_pumped_water_sco_pumping": MarketSeries("eskom_pumped_water_sco_pumping", "Eskom Pumped Water SCO Pumping", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_thermal_generation": MarketSeries("eskom_thermal_generation", "Eskom Thermal Generation", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_nuclear_generation": MarketSeries("eskom_nuclear_generation", "Eskom Nuclear Generation", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_international_imports": MarketSeries("eskom_international_imports", "Eskom International Imports", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_eskom_ocgt_generation": MarketSeries("eskom_eskom_ocgt_generation", "Eskom OCGT Generation", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_eskom_gas_generation": MarketSeries("eskom_eskom_gas_generation", "Eskom Gas Generation", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_dispatchable_ipp_ocgt": MarketSeries("eskom_dispatchable_ipp_ocgt", "Eskom Dispatchable IPP OCGT", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_hydro_water_generation": MarketSeries("eskom_hydro_water_generation", "Eskom Hydro Water Generation", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_pumped_water_generation": MarketSeries("eskom_pumped_water_generation", "Eskom Pumped Water Generation", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_ios_excl_ils_and_mlr": MarketSeries("eskom_ios_excl_ils_and_mlr", "Eskom IOS (excl ILS/MLR)", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_ils_usage": MarketSeries("eskom_ils_usage", "Eskom ILS Usage", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_manual_load_reduction_mlr": MarketSeries("eskom_manual_load_reduction_mlr", "Eskom Manual Load Reduction", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_wind": MarketSeries("eskom_wind", "Eskom Wind (Station Build-Up)", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_pv": MarketSeries("eskom_pv", "Eskom PV (Station Build-Up)", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_csp": MarketSeries("eskom_csp", "Eskom CSP (Station Build-Up)", "MW", "hourly", "eskom_station_buildup", "eskom"),
    "eskom_other_re": MarketSeries("eskom_other_re", "Eskom Other RE (Station Build-Up)", "MW", "hourly", "eskom_station_buildup", "eskom"),
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
