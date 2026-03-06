# Zorora

![License](https://img.shields.io/badge/License-AGPLv3%2B%20%7C%20Commercial-blue.svg)
![Tests](https://github.com/AsobaCloud/zorora/actions/workflows/test.yml/badge.svg)

Zorora is a local-first deep research and analysis tool for policy, market, and technical intelligence. It runs against local LLM endpoints, supports both terminal and web interfaces, and handles everything from source discovery to structured data analysis.

**Learn more in the [full documentation](https://code.asoba.co)**.

![Zorora Web UI](docs/ui.png)

## Features

- **Deep research** — intent refinement + query decomposition across newsroom/web/academic sources, relevance-first then credibility ranking, and contract-based synthesis (outline → section expansion) with inline citations and no raw dump fallback
- **Comparative queries** — auto-detects "X vs Y" queries and generates dimension-based comparison tables
- **Source quality** — credibility scoring, cross-reference detection, and full article content extraction for grounded analysis
- **Data analysis** — sandboxed Python execution with pandas, numpy, and matplotlib for structured dataset workflows
- **Multi-provider LLM** — local models via LM Studio, plus HuggingFace, OpenAI, and Anthropic adapters
- **Dual interfaces** — terminal REPL with Rich UI and web UI with two-column research layout and persistent history sidebar
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
