"""SEP-055: Verify CI config stub includes all attributes that tests reference."""
import importlib
import importlib.util
import tempfile
import os
from pathlib import Path


def _load_ci_stub(module_name="ci_config"):
    """Load the CI config stub CONFIG string and import it as a module."""
    gen_path = Path(__file__).parent.parent / ".github" / "generate_ci_config.py"
    spec = importlib.util.spec_from_file_location("_gen", gen_path)
    gen_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_mod)
    config_source = gen_mod.CONFIG

    tmp = tempfile.mkdtemp()
    stub_file = os.path.join(tmp, "config.py")
    with open(stub_file, "w") as f:
        f.write(config_source)

    spec = importlib.util.spec_from_file_location(module_name, stub_file)
    ci_config = importlib.util.module_from_spec(spec)
    ci_config.__dict__["os"] = os
    spec.loader.exec_module(ci_config)
    return ci_config


def test_ci_config_stub_has_all_required_attributes():
    """Generate the CI config stub and verify it has all attributes tests depend on."""
    ci_config = _load_ci_stub("ci_config_attrs")

    required_attrs = [
        "DEPTH_PROFILES",
        "RESEARCH_TYPES",
        "QUERY_DECOMPOSITION",
        "CONTENT_FETCH",
        "MODEL_BUDGETS",
        "SYNTHESIS",
        "OPENALEX",
        "SEMANTIC_SCHOLAR",
        "WORLD_BANK",
        "CONGRESS_GOV",
        "GOVTRACK",
        "FEDERAL_REGISTER",
        "SEC_EDGAR",
        "CROSSREF",
        "ARXIV",
        "WORLD_BANK_INDICATORS",
        "FRED",
        "EIA",
        "OPENEI",
        "REGULATORY",
        "ALERTS",
        "YFINANCE",
        "MARKET_DATA",
        "IMAGING",
        "SAPP",
        "ESKOM",
        "EMBER",
        "GCCA",
    ]

    missing = [attr for attr in required_attrs if not hasattr(ci_config, attr)]
    assert not missing, f"CI config stub missing attributes: {missing}"


def test_ci_config_stub_has_eskom_fetch_urls():
    """ESKOM config must include fetch_urls for HTTP auto-fetch tests."""
    ci_config = _load_ci_stub("ci_config_eskom")

    assert hasattr(ci_config, "ESKOM"), "ESKOM config block missing"
    eskom = ci_config.ESKOM
    assert "fetch_urls" in eskom, "ESKOM must have fetch_urls"
    assert "eskom.co.za" in eskom["fetch_urls"].get("demand", ""), \
        "ESKOM fetch_urls.demand must reference eskom.co.za"
