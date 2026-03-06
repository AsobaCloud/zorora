# Changelog

All notable changes to Zorora are documented here, organized by milestone in reverse chronological order.

## 2026-03-06 — v3.5.0: Deep Research Contracts and Retrieval Expansion

Deep research was upgraded to a contract-driven synthesis pipeline with stricter quality gates, expanded search surfaces, structured source integrations, and no raw evidence-dump fallback behavior.

- `df39e22` Finalize synthesis #4 contract with no-dump fallback and stricter quality gates
- `05c6ca4` SEP-032: Add structured data sources (CrossRef, arXiv, World Bank) with caching
- `5cc220c` Enforce synthesis contracts and strengthen deterministic section synthesis
- `bdf5f93` Harden synthesis quality gates and reduce aggressive fallback
- `88149f2` Improve synthesis resilience with market context integration and section retry
- `188667e` Add cold-start retries and relax citation cap for synthesis quality
- `e526033` Use credibility-ranked source excerpts for deterministic section synthesis
- `bddea1c` Improve deep research evidence quality and synthesis fallback behavior
- `25f294a` SEP-031: Add 6 new search surfaces to deep research pipeline
- `2f029f1` Improve deep research synthesis path and quality gating
- `4725d54` Harden deep research retrieval and synthesis quality gates
- `047884d` Stabilize deep research flow and synthesis fallbacks
- `4205830` SEP-028: Strip all markdown header levels in section expansion
- `046c9a3` SEP-022: Fix deep research pipeline — 6 bugs causing irrelevant results
- `0623891` SEP-021: Add yfinance provider for renewable metals and ETF proxies

## 2026-03-03 — Deep Research Architecture (SEP-019)

Ground-truth architecture overhaul: structured data flow, two-stage synthesis, and quality signals.

- `f3b1d4a` SEP-019: Quality signals — stemming, cross-ref fix, freshness bonus
- `d7a1f82` SEP-019: Structured data flow — bypass string→parse round-trip
- `53fd075` SEP-019: Two-stage synthesis pipeline (outline → per-section expansion)
- `d15c437` SEP-019: Centralize synthesis/clustering limits and strip metadata from prompts

## 2026-03-03 — Comparative Query Support (SEP-018)

Auto-detect "X vs Y" queries with dimension-based comparison synthesis.

- `575877b` SEP-018: Resolve generic comparison subjects via preliminary search
- `ffa4a2d` SEP-018: Add comparative query detection and comparison synthesis template

## 2026-03-02 — UI and Pipeline Improvements (SEP-007 through SEP-017)

Web UI layout overhaul, relevance filtering, clustering caps, and operational fixes.

- `57128da` SEP-016: Set 15s timeout on query refinement to prevent indefinite hang
- `ab45303` SEP-017: Add StreamHandler to web UI logging for console output
- `9304160` SEP-014: Fix Discuss button by adding escapeAttr() for onclick attributes
- `12b2c94` SEP-010: Replace inline history panel with persistent left sidebar
- `1dfcbf3` SEP-009: Cap clustering input to top-25 relevance-sorted sources
- `dff4018` SEP-008: Add relevance filtering to deep research pipeline
- `8ee06e2` SEP-007: Two-column research layout with integrated chat synthesis

## 2026-03-01 — Content and Chat (SEP-004, SEP-005, SEP-006)

Full-content fetching and grounded follow-up chat.

- `70fa3c7` SEP-006: Fix Ruff E741 lint error in deep_research_service.py
- `1371f8d` SEP-005: Add full-content fetching for deep research sources
- `ad24f64` SEP-004: Ground follow-up chat in source content snippets

## 2026-02-28 — Foundation SEPs (SEP-001 through SEP-003)

HuggingFace adapter, depth profiles, and project hygiene.

- `3159706` SEP-003: Add depth profiles, multi-query search, and knowledge fallback
- `92670c7` SEP-002: Add streaming tests for HuggingFaceAdapter
- `377714e` SEP-002: Add HuggingFaceAdapter for native HF Inference Toolkit endpoints
- `071bb7f` SEP-001: Add direnv files to .gitignore

## 2026-02-19 — Post-v3.0 CI, Tests, and Docs Hardening

Stabilized CI and test collection after v3.0.0, plus README and project scaffolding updates.

- `b66748d` Add community health files and README badges
- `ec41e7d` Fix hardcoded local path in test_shared_research_paths.py
- `04a5b1c` Fix CI: generate stub config.py (the real one is gitignored)
- `e967c50` Add root conftest.py to fix bare module imports in CI
- `1f96f84` Fix CI: use non-editable install to resolve import config
- `9869e8a` Fix CI test collection: add PYTHONPATH and fix hardcoded path
- `40e9ff5` Fix CI: install pytest in test workflow
- `e99cdb6` Slim README to quick-start landing page
- `c256561` Add non-LLM integration tests and CI workflow
- `998700a` Implement SEP DA issues 001-007 for data analysis workflow
- `9cb300e` Rewrite README as docs router

## 2026-02-15 — v3.0.0: Data Analysis Engine

Sandboxed Python execution for dataset workflows, plus CI pipeline and community health files.

- `b66748d` Add community health files and README badges
- `c256561` Add non-LLM integration tests and CI workflow
- `998700a` Implement SEP DA issues 001-007 for data analysis workflow
- `db89551` v3.0.0 — data analysis engine, sandboxed execution, dataset workflows

## 2026-02-09 — v2.6.0: Unified Research & Chat UX

Session chat, streaming replies, source discuss actions, and unified research execution.

- `0b19975` Replace mock-heavy dispatch tests with real file-op end-to-end tests
- `fd8e98a` Add streaming chat replies and source discuss quick actions
- `d7f5c18` Add session chat UX, follow-up chat APIs, and history UX controls
- `c8e4419` Unify research execution and harden REPL command flow

## 2026-01-14 — v2.3.0–v2.5.0: Tool Registry & Deep Command

Tool registry migration, /deep command, /digest news analysis, and newsroom enhancements.

- `b462d25` Add municipality detection for Nehanda RAG requests
- `2e3b61f` Rename EnergyAnalyst to Nehanda throughout codebase
- `362f1a1` Add /digest command for news trend analysis by continent
- `c9e37c2` Add newsroom caching and natural language search support
- `67c6e01` Add JWT authentication for newsroom API with clear error messages
- `274466c` Complete tool registry migration and enhance /code file editing
- `b8f31c5` Add /deep command and improve offline coding reliability
- `960c331` Fix SQLite threading, add progress feedback, improve source display

## 2025-12-28 — v2.0.0: Web UI & Multi-Provider

Web-based deep research interface, multi-provider LLM support (OpenAI, Anthropic), settings modal, and ONA platform integration.

- `88a6eba` Add beautiful progress display with hierarchical tool visualization
- `89562e8` Implement boxed input UI using prompt_toolkit Application/Frame/Layout
- `a262ad7` Implement end-to-end validation script for Zorora ↔ ONA Platform
- `4c10455` Add remote command backend capability for ONA platform integration
- `8c6687d` Add multi-provider API support (OpenAI and Anthropic)
- `053c266` Implement settings modal feature
- `7b5b27e` Add OpenAI and Anthropic API key and endpoint support to settings modal
- `9e94dbe` Add per-endpoint API key support to endpoint modal
- `3b263ba` Implement deep research feature — Phases 1-4 complete
- `9fe2c00` Add web UI for deep research interface

## 2025-12-15 — v1.0.0: Initial Release

Zorora REPL with Rich UI, multi-model delegation, web search, newsroom integration, academic sources, image generation, and specialist model routing.

- `8d57e29` Add Apache 2.0 license and v1.0.0 release notes
- `c5eba52` Reorganize codebase: move deprecated files, streamline README, add detailed docs
- `a156f58` Add /academic command with multiple sources and Sci-Hub integration
- `768d10a` Enrich web search with academic sources (Scholar + PubMed)
- `84f8495` Implement 4-phase intelligent routing system for improved 4B model performance
- `ebc4080` Add text-to-image generation with Flux Schnell
- `191d021` Implement context summarization for better VRAM management
- `f9134e2` Add image analysis tool with VL model support
- `4d3ac4d` Add conversation persistence and interrupt handling
- `9c91392` Add HuggingFace inference endpoint support
- `bbc6590` Enhance web search with Brave API, caching, parallel search, and improved logging
- `b0a6cad` Add get_newsroom_headlines tool for efficient article fetching
- `7ee0fcd` Add multi-model delegation with text parsing workaround
- `6b629ee` Initial commit: Zorora REPL with Rich UI
