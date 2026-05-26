**Status: DONE** — Completed 2026-03-12 (751acc6)

# SEP-038: Domain-aware diligence synthesis with per-chapter analytical prompting

## Context

The diligence synthesis pipeline has three compounding failures that prevent it from ever producing a useful LLM-generated report:

1. **Quality gate rejects all diligence output.** `_passes_direct_synthesis_quality_gate` (synthesizer.py:2511) requires a "Direct Answer" section. Diligence reports have domain sections (Tariff & Revenue, Regulatory & Licensing, etc.) — no "Direct Answer." Every diligence synthesis fails the gate, retries, fails again, falls back to keyword extraction.

2. **Repair function caps sections at 3.** `_repair_direct_synthesis_output` (synthesizer.py:2488) limits thematic sections to 3 via `thematic_sections_kept >= 3`. Diligence needs 5+ domain sections. Even if the quality gate passed, the repair function would drop half the report.

3. **LLM prompt is a flat blob.** `_build_diligence_synthesis_prompt` (synthesizer.py:1973) dumps all 25 sources as a flat ranked list via `_format_direct_sources_for_prompt`. The model gets no guidance on which sources are for which chapter, no analytical questions per section — just "here are sources, write 6 sections."

**Evidence:** Every diligence search logs `"Direct synthesis failed quality gate after retry; using deterministic fallback"` (synthesizer.py:2849). The deterministic fallback produces extractive keyword summaries, not analysis.

## Objective

Make the diligence synthesis pipeline produce an LLM-generated report where each chapter contains actual analysis of domain-specific sources, with per-section analytical questions, and a quality gate that validates the diligence output format (not the generic "Direct Answer" format).

**Behavioral acceptance criteria:** A Lesotho solar diligence search produces a report where:
1. The LLM synthesis is NOT thrown away by the quality gate
2. Each section contains analysis grounded in sources from that domain
3. The model was explicitly asked domain-specific analytical questions (e.g., "What are the licensing requirements in Lesotho?")

## Scope

- /Users/shingi/Workbench/zorora/workflows/deep_research/synthesizer.py
- /Users/shingi/Workbench/zorora/tests/test_sep036.py

## Justification

The regular deep research path (`_build_direct_synthesis_prompt`, `_repair_direct_synthesis_output`, `_passes_direct_synthesis_quality_gate`) is designed for open-ended research with a "Direct Answer" + thematic sections format. Diligence has a fundamentally different output structure (6 fixed domain sections, no "Direct Answer"). Reusing the regular path guarantees failure. Per the user's direction: create new diligence-specific functions while reusing shared utilities (DRY).

**Sources consulted:**
- `synthesizer.py:2511` — quality gate requires "Direct Answer" (confirmed by reading)
- `synthesizer.py:2488` — repair caps at 3 thematic sections (confirmed by reading)
- `synthesizer.py:1973-2040` — current diligence prompt is flat blob (confirmed by reading)
- `synthesizer.py:1909-1970` — `_format_direct_sources_for_prompt` (reusable)
- `synthesizer.py:2637-2643` — `_DILIGENCE_DOMAIN_SECTIONS` domain→title mapping (reusable)
- `synthesizer.py:190-235` — `_call_research_synthesis_model` (reusable)
- `synthesizer.py:2419-2421` — `_ensure_direct_answer_definition` returns text unchanged when no "Direct Answer" section exists (safe)

## Design

### Constraint: No changes to regular deep research

All new functions are diligence-specific. `_build_direct_synthesis_prompt`, `_repair_direct_synthesis_output`, `_passes_direct_synthesis_quality_gate`, and `_DIRECT_RESEARCH_ANALYST_SYSTEM_PROMPT` are not modified.

### 1. New constant: `_DILIGENCE_ANALYST_SYSTEM_PROMPT` (near line 178)

```python
_DILIGENCE_ANALYST_SYSTEM_PROMPT = (
    "You are a senior renewable energy due diligence analyst specializing in "
    "acquisition advisory for power generation assets in emerging markets. "
    "You produce structured diligence reports for investment committees. "
    "For each report section, synthesize the domain-specific sources provided, "
    "quantify where data permits, flag material gaps, and cite inline using "
    "exact source titles in square brackets. "
    "Do not produce planning steps, meta commentary, or procedural narration."
)
```

### 2. New constant: `_DILIGENCE_SECTION_QUESTIONS` (near `_DILIGENCE_DOMAIN_SECTIONS`)

Maps domain key → parameterized analytical question template:

```python
_DILIGENCE_SECTION_QUESTIONS = {
    "commercial": (
        "What are the specific electricity tariff rates, PPA terms, and feed-in tariff "
        "structures in {country}? Estimate annual revenue for a {capacity_mw}MW "
        "{technology} plant using the local data context."
    ),
    "licensing": (
        "What specific permits, licenses, and regulatory approvals are required to "
        "develop and operate a {technology} power plant in {country}? Identify the "
        "regulator and licensing process."
    ),
    "environmental": (
        "What environmental impact assessment requirements and grid connection "
        "procedures apply to a {capacity_mw}MW {technology} plant in {country}?"
    ),
    "performance": (
        "What are measured capacity factors and performance ratios for operational "
        "{technology} plants in {country} or comparable markets? How does this asset "
        "compare to the benchmark?"
    ),
    "counterparty": (
        "Who are the key counterparties — offtaker, grid operator, developer — "
        "and what is their track record in {country}?"
    ),
    "asset_specific": (
        "What is known about {name} specifically — ownership changes, financing, "
        "operational history, recent news?"
    ),
}
```

### 3. New function: `_format_sources_by_domain(sources) -> dict[str, str]`

Groups sources by `intent_domain`, formats each group using the existing `_format_direct_sources_for_prompt`. Returns `{domain_key: formatted_text}`. Sources with empty/missing `intent_domain` go into `"other"`.

### 4. New function: `_build_diligence_synthesis_prompt_v2(state, diligence_context, asset_metadata) -> str`

Replaces `_build_diligence_synthesis_prompt` in the code path (original kept for reference).

Structure:
```
Today's date is {date}. Produce a structured acquisition diligence report.

{asset_block}
{context_block}

For each section below, analyze the domain-specific sources listed under that section.
Cite inline using exact source titles in square brackets.

## Executive Summary
[2-4 sentences summarizing diligence findings with key risk/opportunity highlights]

## Tariff & Revenue Potential
**Question:** {analytical question for commercial}
**Sources for this section:**
{formatted sources for commercial domain}

## Regulatory & Licensing Requirements
**Question:** {analytical question for licensing}
**Sources for this section:**
{formatted sources for licensing domain}

[... for all 6 sections ...]

## Risk Summary & Recommendation
[Synthesize across all domains: key risks, mitigants, acquisition recommendation]
```

If a domain has zero sources: "No sources were retrieved for this domain. State this gap explicitly and provide brief [Background Knowledge] if possible."

### 5. New function: `_passes_diligence_quality_gate(text, state) -> bool`

Checks:
- At least 4 sections
- First section is "Executive Summary"
- At least 3 of the 6 diligence section titles present (fuzzy substring match against `_DILIGENCE_DOMAIN_SECTIONS` values)
- Minimum source citations (same logic as regular gate)
- Executive summary not generic (`_summary_needs_rewrite`)
- Per-section: not empty, no low-value patterns

Does NOT check for "Direct Answer". Does NOT call `_direct_answer_covers_definition`.

### 6. New function: `_repair_diligence_synthesis_output(text, state) -> str`

Lighter version of `_repair_direct_synthesis_output`:
- Normalizes section titles
- Drops "sources", "gaps", "caveats" sections (same as regular)
- Does NOT cap thematic sections at 3 (diligence needs 5+)
- Does NOT call `_ensure_direct_answer_definition`
- Applies `_mark_background_knowledge_sentences` and `_salvage_inline_citations` per section (reuses existing helpers)

### 7. Wire into `synthesize_direct()` (line 2781)

The `is_diligence` branch changes:

```python
if is_diligence:
    prompt = _build_diligence_synthesis_prompt_v2(state, ...)
    system_prompt = _DILIGENCE_ANALYST_SYSTEM_PROMPT
else:
    prompt = _build_direct_synthesis_prompt(state, ...)
    system_prompt = _DIRECT_RESEARCH_ANALYST_SYSTEM_PROMPT

raw = _call_research_synthesis_model(prompt, system_prompt=system_prompt)

# Normalize
if is_diligence:
    normalized = _repair_diligence_synthesis_output(normalized, state)
else:
    normalized = _repair_direct_synthesis_output(normalized, state)

# Quality gate
if is_diligence:
    passes = _passes_diligence_quality_gate(normalized, state)
else:
    passes = _passes_direct_synthesis_quality_gate(normalized, state)

# Retry and fallback logic unchanged in structure
```

### Shared utilities reused (not modified)

- `_call_research_synthesis_model` — LLM call with retry
- `_format_direct_sources_for_prompt` — source formatting with budget
- `_parse_markdown_sections` — markdown parsing
- `_extract_markdown_section` / `_replace_markdown_section` / `_insert_after_section`
- `_count_ranked_source_citations` / `_has_ranked_source_citation`
- `_summary_needs_rewrite`
- `_normalize_outline_headers` / `_normalize_direct_citation_labels`
- `_mark_background_knowledge_sentences` / `_salvage_inline_citations`
- `_deterministic_diligence_synthesis` — fallback (unchanged)
- `generate_diligence_charts` — chart insertion (unchanged)
- `_DILIGENCE_DOMAIN_SECTIONS` — domain→title mapping (unchanged)

## Success Criteria

1. Diligence LLM synthesis passes the quality gate (not rejected for missing "Direct Answer")
2. Each section in the LLM prompt contains only that domain's sources + an analytical question
3. The system prompt is diligence-specific (investment committee audience, domain analysis)
4. Regular deep research is completely unaffected — no shared functions modified
5. All existing + new tests pass
6. Real Lesotho diligence search produces LLM-generated report with domain-specific analysis (or populated deterministic fallback if LLM unavailable)

## Validation

**Verified (by reading code):**
- Quality gate at line 2511 requires "Direct Answer" — diligence never has one → always fails
- Repair at line 2488 caps thematic sections at 3 — diligence needs 5+ → drops sections
- `_ensure_direct_answer_definition` at line 2419-2421 returns text unchanged when no "Direct Answer" section → safe to skip but also pointless for diligence
- `_format_direct_sources_for_prompt` works on any source list → reusable per-domain
- `_DILIGENCE_DOMAIN_SECTIONS` already maps domain keys to section titles → reusable

**External sources validating the architecture:**
1. Palantir LLM Prompt Engineering Best Practices (https://www.palantir.com/docs/foundry/aip/best-practices-prompt-engineering) — recommends breaking complex tasks into structured sub-tasks with specific instructions per section ("prompt chaining"), providing only the relevant context for each sub-task rather than dumping all context at once, and assigning domain-specific roles to guide tone and analytical depth.
2. Prompt Engineering Guide — RAG for LLMs (https://www.promptingguide.ai/research/rag) — documents that section-packed long-context grounding improves long-form reporting by packing section-specific evidence and pruning redundant context. Also: quality gates should validate section-level evidence coverage, not generic structural markers.
3. MEGA-RAG: Multi-Evidence Guided Answer Refinement (https://pmc.ncbi.nlm.nih.gov/articles/PMC12540348/) — demonstrates that conditioning generation on multi-source evidence context with per-section diversity and verifiable citations reduces hallucination and improves grounding, directly supporting our per-domain source grouping approach.

**Assumed:**
- LLM will produce better output with domain-grouped sources + analytical questions vs flat dump (high confidence per external sources above)
- The reasoning model endpoint may be unavailable (cold start), so deterministic fallback remains important as backup

**Known gaps:**
- Sources without `intent_domain` fall to "other" bucket — not surfaced to any specific section
- Quality of analytical questions depends on asset metadata completeness (country, capacity, technology)

## Objective Verification

Run a diligence search for a Lesotho solar asset. Verify:
1. Logs do NOT show "Direct synthesis failed quality gate" (or if LLM unavailable, that's a different failure)
2. The synthesis output contains domain-specific analysis (not keyword-extracted sentences)
3. If LLM is unavailable, the deterministic fallback still produces populated domain sections (existing behavior preserved)
