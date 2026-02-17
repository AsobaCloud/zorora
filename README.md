# Zorora

Local-first deep research and analysis for policy, market, and technical intelligence.

This repository README is intentionally short. Zorora's full documentation lives at **[code.asoba.co](https://code.asoba.co)**.

![Zorora Web UI](docs/ui.png)

## Start Here

- Full docs: [code.asoba.co](https://code.asoba.co)
- GitHub repo: [AsobaCloud/zorora](https://github.com/AsobaCloud/zorora)

## Quick Start

### Prerequisites

- Python 3.8+
- LM Studio (default local endpoint: `http://localhost:1234`)

### Install

```bash
pip install git+https://github.com/AsobaCloud/zorora.git
```

Or from source:

```bash
git clone https://github.com/AsobaCloud/zorora.git
cd zorora
pip install -e .
```

### Run

Terminal UI:

```bash
zorora
```

Web UI:

```bash
zorora web
# http://localhost:5000
```

## Local Reference Docs

Use these for contributor context while the canonical docs live on `code.asoba.co`:

- Commands: [COMMANDS.md](COMMANDS.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Workflows: [docs/WORKFLOWS.md](docs/WORKFLOWS.md)
- Development: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Data analysis specification: [docs/data_analysis_spec.docx](docs/data_analysis_spec.docx)

## License

See [LICENSE.md](LICENSE.md).
