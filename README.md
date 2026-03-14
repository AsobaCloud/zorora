# Zorora

![License](https://img.shields.io/badge/License-AGPLv3%2B%20%7C%20Commercial-blue.svg)
![Tests](https://github.com/AsobaCloud/zorora/actions/workflows/test.yml/badge.svg)

Zorora is a local-first energy intelligence platform for acquisition diligence, regulatory monitoring, geospatial asset discovery, and market analysis. Built for energy traders and asset investors, it runs against local LLM endpoints with both terminal and web interfaces — all data stays on your machine.

Current stable release: **v3.6.0** (March 13, 2026).

**Learn more in the [full documentation](https://code.asoba.co)**.

![Zorora Web UI](docs/ui.png)

## Platform Modes

- **Deep Research** — multi-source research across academic, web, and newsroom sources with credibility scoring, citation graphs, and contract-based synthesis with inline citations
- **Diligence Search** — brownfield acquisition due diligence with domain-specific analysis (tariffs, regulations, performance, vendors), structured data from EIA/utility/World Bank databases, and automated diligence reports with embedded charts
- **Digest** — stage articles and market datasets, then synthesize structured energy market and policy digests
- **Alerts** — monitor topics and sources for new developments with configurable alert rules
- **Regulatory** — track renewable portfolio standards, utility rates, generation assets, and regulatory environments by jurisdiction
- **Global View** — interactive country map with click-to-filter topic/source popups and market dataset cards
- **Imaging** — Leaflet-based OSINT geospatial view for mineral deposits, concessions, and generation assets with viability scoring overlays

## Additional Capabilities

- **Data analysis** — sandboxed Python execution with pandas, numpy, and matplotlib for structured dataset workflows
- **Comparative queries** — auto-detects "X vs Y" queries and generates dimension-based comparison tables
- **Source quality** — credibility scoring, cross-reference detection, and full article content extraction
- **Multi-provider LLM** — local models via LM Studio, plus HuggingFace, OpenAI, and Anthropic adapters
- **Dual interfaces** — terminal REPL with Rich UI and web UI with persistent history sidebar
- **Follow-up chat** — conversational follow-ups grounded in source content snippets

## Configuration

Research depth profiles, model budgets, and synthesis settings are configured in `config.py`. See the [full documentation](https://code.asoba.co) for details.

## Get Started

For detailed setup instructions, see the [setup documentation](https://code.asoba.co).

1. Install Zorora:

    ```bash
    pip install git+https://github.com/AsobaCloud/zorora.git
    ```

    Or from source:

    ```bash
    git clone https://github.com/AsobaCloud/zorora.git
    cd zorora
    pip install -e .
    ```

2. Run Zorora:

    ```bash
    zorora
    ```

    Or launch the web UI:

    ```bash
    zorora web
    ```

## Reporting Issues

File a [GitHub issue](https://github.com/AsobaCloud/zorora/issues) to report bugs or request features.

## License

Dual-licensed:

- AGPLv3+ for open-source use
- Commercial license available from AsobaCloud for organizations that want to commercialize without AGPL reciprocity obligations

See [LICENSE.md](LICENSE.md).
