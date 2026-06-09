# Zorora System Map: Current State (June 2026)

## 1. Core Architecture (The Deterministic Brain)
Zorora is a **Deterministic Energy & Market Intelligence Engine**. It operates without LLM orchestration, using pattern matching to route queries to hardcoded, reliable pipelines.

-   **Routing**: `simplified_router.py` (Deterministic tree).
-   **Execution**: Fixed-pipeline execution via `turn_processor.py` and `engine/deep_research_service.py`.
-   **Inference**: Hybrid Local (4B) + Remote (HF/OpenAI/Anthropic) model support.
-   **Primary Source**: [ARCHITECTURE.md](ARCHITECTURE.md)

## 2. Specialized Intelligence Domains
Zorora is mapped into 4 primary intelligence domains, each with dedicated toolsets and workflows.

### A. Energy & GIS Intelligence (`tools/imaging/`, `workflows/feasibility.py`)
-   **Site Scoring**: `site_score.py` (GIS-based location analysis).
-   **Resource Mapping**: `resource_client.py`, `gcca_client.py`.
-   **Project Viability**: `viability.py` (Energy project feasibility studies).
-   **Mineral Resources**: `mrds_client.py` (Global mineral data).

### B. Market & Economic Intelligence (`tools/market/`, `workflows/market_workflow.py`)
-   **Power Markets**: `eskom_client.py`, `sapp_client.py` (Southern African Power Pool).
-   **Global Energy Data**: `ember_client.py` (Global power stats).
-   **Economic Indicators**: `fred_client.py`, `worldbank_client.py`, `yfinance_client.py`.

### C. Regulatory & Policy Intelligence (`tools/regulatory/`, `workflows/regulatory_workflow.py`)
-   **Tariff Analysis**: `eskom_tariff_client.py` (NERSA/Eskom tariff tracking).
-   **Policy Standards**: `rps_client.py` (Renewable Portfolio Standards).
-   **Global Legislation**: Integrated RSS/Direct scraper suite (US/UK/EU/SA).

### D. Global Newsroom Suite (`infra/lambda/newsroom_scraper/`)
-   **Centralized Ingestion**: 4 specialized scrapers (News, Legislation, Polymarket, Economy).
-   **Storage Contract**: DynamoDB `newsroom_articles` (Single-Table Design).
-   **Primary Source**: [INGESTION_CONTRACT.md](INGESTION_CONTRACT.md)

## 3. Product Feature Suite
-   **Deterministic Deep Research**: High-credibility synthesis with multi-source ranking.
-   **Energy Feasibility Studies**: Automated rubric-based site evaluation (`workflows/feasibility.py`).
-   **Market Series Analysis**: Multi-indicator trend analysis (`tools/market/series.py`).
-   **Legislative Watchdog**: Real-time regulatory feed monitoring.
-   **Digest Synthesis**: Automated newsletter/digest generation (`workflows/digest_workflow.py`).
-   **Alerting System**: Real-time threshold monitoring (`workflows/alert_runner.py`).

## 4. UI/UX Ecosystem
### Web UI (`ui/web/`)
-   **Async Synthesis**: Real-time research progress updates.
-   **Visual Settings**: Model role management (7+ roles) and masked API key storage.
-   **Newsroom Browser**: Faceted library browsing (Continent/Topic/Source).

### Terminal REPL (`repl.py`)
-   **Specialized Modes**: `/develop` (Code), `/deep` (Research), `/ask` (QA).
-   **Command Extensions**: `/load_dataset`, `/feasibility`.

## 5. Infrastructure Map
-   **Primary Region (af-south-1)**: ECS Fargate (Web UI), Lambda Scrapers, S3 Assets.
-   **Database Region (us-east-1)**: DynamoDB (User Auth, Subscriptions, Newsroom Articles).
-   **Configuration**: AWS SSM Parameter Store (API keys for EIA, Brave, HF, etc.).
-   **Security**: Tiered JWT-based gating (Explorer, Professional, Enterprise).
-   **Primary Source**: [INFRASTRUCTURE.md](INFRASTRUCTURE.md)
