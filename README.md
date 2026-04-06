# Zorora

![License](https://img.shields.io/badge/License-AGPLv3%2B%20%7C%20Commercial-blue.svg)
![Tests](https://github.com/AsobaCloud/zorora/actions/workflows/test.yml/badge.svg)

Zorora is a local-first energy intelligence platform for acquisition diligence, regulatory monitoring, geospatial asset discovery, and market analysis. Built for energy traders and asset investors, it runs against local LLM endpoints with web and terminal interfaces — all data stays on your machine.

For customer-facing deployments, the **web UI is the primary product surface**. Legacy REPL development/code-generation commands are intended for internal/operator use.

**Learn more in the [full documentation](https://code.asoba.co)**.

![Zorora Web UI](docs/ui.png)

## Platform Modes

Zorora provides seven integrated intelligence modes:

- **Deep Research** — multi-source research across academic, web, and newsroom sources with credibility scoring, citation graphs, and evidence-grounded synthesis with inline citations. Includes research memory: thumbs up/down feedback on responses, persistent chat threads across restarts, and automatic injection of scouting feasibility findings as internal RAG sources.

- **Digest** — stage articles and market datasets, then synthesize structured energy market and policy digests with paginated article retrieval.

- **Alerts** — monitor topics and sources for new developments with configurable alert rules and execution history.

- **Regulatory** — track renewable portfolio standards, utility rates, generation assets, and regulatory environments by jurisdiction. Covers EIA data, OpenEI utility rates, NERSA events, and IPP Office filings.

- **Global View** — interactive country map with click-to-filter topic/source popups and market dataset cards showing real-time commodity, FX, and energy market data.

- **Discovery** — Leaflet-based geospatial view for mineral deposits (USGS MRDS), generation assets (GEM), GCCA transmission zones, substations, and supply areas with viability scoring overlays.

- **Scouting** — kanban pipeline for brownfield, greenfield, and BESS site evaluation with 5-stage tracking (identified, scored, feasibility, diligence, decision). Includes automated feasibility studies across five dimensions: production, trading, grid, regulatory, and financial — each with LLM-synthesized conclusions, risk assessments, and confidence ratings. Greenfield and BESS sites are scored using NASA POWER resource data, grid proximity, DAM arbitrage spreads, and TOU tariff differentials.

## Data Sources

Zorora ingests 80 market series across 6 providers, refreshed automatically via background threads:

| Provider | Series | Frequency | Coverage |
|----------|--------|-----------|----------|
| **FRED** | 13 | Daily | Oil, gas, coal, uranium, treasuries, FX (ZAR/USD, ZMW/USD), policy rates |
| **yfinance** | 12 | Daily | Gold, copper, silver, platinum, palladium, aluminum, iron ore, lithium/uranium/rare earth ETFs |
| **World Bank** | 18 | Annual | SADC electricity indicators — coal %, renewables %, T&D loss %, access %, per-capita consumption for ZA/ZW/MZ/ZM |
| **Ember Energy** | 8 | Monthly | South Africa and Zimbabwe coal, wind, solar generation, demand, total gen, renewables share |
| **SAPP** | 6 | Hourly | DAM prices for RSA-North, RSA-South, Zimbabwe in USD and ZAR |
| **Eskom** | 27 | Hourly | System demand (4 series), RE generation (4 series), station-level build-up (19 series) |

**On-demand sources** (fetched per request, not background-refreshed):
- NASA POWER — solar irradiance, wind speed, temperature for greenfield site scoring
- USGS MRDS — mineral deposit locations for Discovery map
- Newsroom (Ona) — curated energy news articles with 1-hour cache
- Academic search — PubMed, OpenAlex, Semantic Scholar for Deep Research
- Brave Search — web and news results for Deep Research
- World Bank Documents — policy and development reports
- Congress.gov / Federal Register — US policy and regulatory filings
- SEC EDGAR — corporate filings and financial statements
- Local SME corpus — optional Markdown or PDF knowledge base for diligence-mode Deep Research (`data/sme_orthodoxies/`, PDF text via `pypdf`)

## Additional Capabilities

- **Diligence search** — brownfield acquisition due diligence with domain-specific analysis (tariffs, regulations, performance, vendors) and automated diligence reports
- **Comparative queries** — auto-detects "X vs Y" queries and generates dimension-based comparison tables
- **Source quality** — multi-factor credibility scoring, cross-reference detection, predatory publisher filtering, and full article content extraction
- **Research memory** — thumbs up/down feedback persisted to SQLite, chat thread persistence across restarts, and scouting feasibility findings injected as internal sources during research
- **Market data cache** — in-memory cache with 60-second TTL for the market/latest endpoint, reducing 160+ SQLite queries to a single cache hit
- **Multi-provider LLM** — local models via LM Studio, plus HuggingFace, OpenAI, and Anthropic adapters with specialized model roles (reasoning, codestral, vision, search)
- **Dual interfaces** — terminal REPL with Rich UI and web UI with persistent history sidebar
- **Follow-up chat** — conversational follow-ups grounded in source content with streaming SSE responses

## Deployment

### Local

```bash
pip install git+https://github.com/AsobaCloud/zorora.git
zorora web
```

Or from source:

```bash
git clone https://github.com/AsobaCloud/zorora.git
cd zorora
pip install -e .
zorora web
```

On macOS (and other PEP 668–managed Python installs), create a virtual environment before `pip install` so dependencies such as `rich` resolve correctly:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
pytest
```

### Docker

```bash
docker build -t zorora .
docker run -p 5000:5000 -v ~/.zorora:/home/zorora/.zorora zorora
```

The container runs gunicorn with 1 worker and 4 threads. Background data refresh threads start automatically via the `post_worker_init` hook. Health check available at `GET /health`.

### Enterprise (Ona Platform)

Zorora ships as a Fargate service in the Ona platform with permission-gated access via the application card. Deployment is handled by the CI/CD pipeline — pushing to `main` triggers automatic Docker build, ECR push, and ECS service update.

Without a persistent volume, Fargate tasks use **ephemeral** local disk: SQLite files under `/home/zorora/.zorora` are **not** kept across new deployments.

**Recommended:** attach **Amazon EFS in Regional (Multi-AZ) mode** — in the console this is a **Regional** file system (data and metadata replicated across **multiple Availability Zones** in the region). Use **EFS Standard** for the active working set. **Do not** use **One Zone** storage for this path if you want the same durability model as a typical multi-AZ Fargate deployment. Mount the file system at `/home/zorora/.zorora` in the ECS task definition (TLS in transit + IAM optional but common).

**Reference storage price (Africa — Cape Town `af-south-1`, verify live / [EFS pricing](https://aws.amazon.com/efs/pricing/)):** Regional (Multi-AZ) **EFS Standard** is listed at **$0.39 per GB-month** on the public price list (effective date on the offer was 2025-09). Elastic Throughput read/write, lifecycle transitions, and cross-AZ EC2 data transfer are extra line items.

| Regional (Multi-AZ) option | About (USD / GB-month, `af-south-1`) |
|-----------------------------|-------------------------------------:|
| EFS Standard (recommended for this mount) | $0.39 |

Step-by-step **Regional (Multi-AZ) EFS** creation, security groups, IAM, and **ECS task definition JSON** (`volumes` / `mountPoints` for `/home/zorora/.zorora`): [`docs/deployment/ECS_EFS_REGIONAL_MULTIAZ.md`](docs/deployment/ECS_EFS_REGIONAL_MULTIAZ.md).

**Production (`ona-zorora-prod`):** EFS + task definition revision with mount are recorded in [`infra/ona-zorora-prod-efs-applied.md`](infra/ona-zorora-prod-efs-applied.md) (do not duplicate-create the file system).

## Configuration

Research depth profiles, model budgets, and synthesis settings are configured in `config.py`. See the [full documentation](https://code.asoba.co) for details.

### Local SME Corpus (Diligence)

Deep Research diligence runs can include local "subject matter expert" texts that represent different economic, financial, and operational orthodoxies for energy asset management.

- Default folder: `data/sme_orthodoxies/`
- Supported formats: `.md` (with optional frontmatter) and `.pdf` (first N pages extracted; see `pdf_max_pages` in config)
- Template file: `data/sme_orthodoxies/TEMPLATE_sme_orthodoxy.md`
- Config keys: `LOCAL_SME_CORPUS` in `config.py` / `config.docker.py`
- Env overrides:
  - `ZORORA_LOCAL_SME_CORPUS_ENABLED=true|false`
  - `ZORORA_LOCAL_SME_CORPUS_PATH=/absolute/or/relative/path`

These entries are injected as internal evidence during diligence research and can be cited in synthesis like other ranked sources.

**Git-friendly workflow (PDFs are large binaries):** you can keep working PDFs locally, then materialize text as Markdown for the repo — extracted UTF-8 text compresses much better than PDFs in git, and you can edit frontmatter and body like any other SME note.

```bash
python scripts/sme_pdf_to_markdown.py
# Optional: limit pages during extraction
python scripts/sme_pdf_to_markdown.py --max-pages 80
```

If both `Document.pdf` and `Document.md` exist under the corpus folder, the loader uses **only** the `.md` file (single source of truth). After verifying the Markdown, you can delete the PDFs or add `*.pdf` under `data/sme_orthodoxies/` to your `.gitignore`.

### Product Surface Flags

You can control customer-facing surface area with environment flags:

- `ZORORA_WEB_RESEARCH_ENABLED` (default: `true`)
- `ZORORA_WEB_MARKET_INTEL_ENABLED` (default: `true`)
- `ZORORA_REPL_LEGACY_ENABLED` (default: `true` in local config, `false` in docker config)
- `ZORORA_REPL_CODEGEN_ENABLED` (default: `true` in local config, `false` in docker config)

## Reporting Issues

File a [GitHub issue](https://github.com/AsobaCloud/zorora/issues) to report bugs or request features.

## License

Dual-licensed:

- AGPLv3+ for open-source use
- Commercial license available from AsobaCloud for organizations that want to commercialize without AGPL reciprocity obligations

See [LICENSE.md](LICENSE.md).
