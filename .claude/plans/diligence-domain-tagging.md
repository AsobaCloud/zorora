# SEP-037: Tag diligence sources with intent_domain

## Context

The diligence deterministic fallback produces empty domain sections ("No sources found for this domain" × 6) despite 25 sources being retrieved. Root cause: the search loop in `deep_research_service.py` collects sources per intent but never stamps `intent_domain` on them. When `_deterministic_diligence_synthesis` groups by `source.intent_domain`, all 25 sources have `intent_domain=""` and fall into "other" — no domain sections get populated.

**Evidence from logs (`~/.zorora/logs/zorora_20260312.log`):**
- 6 intents ran, each produced scored sources (e.g., intent[5]: 21→9, intent[6]: 30→18)
- 90 total merged to 25 after dedup + budget
- LLM synthesis failed quality gate → deterministic fallback used
- Fallback reported "0 domain(s)" because no source had `intent_domain` set

## Objective

Tag each source with the diligence domain of the intent that found it, so the deterministic fallback can group sources into the correct report sections (Tariff & Revenue, Regulatory & Licensing, Performance, etc.).

## Scope

- /Users/shingi/Workbench/zorora/engine/query_refiner.py
- /Users/shingi/Workbench/zorora/engine/deep_research_service.py
- /Users/shingi/Workbench/zorora/tests/test_sep036.py

## Justification

The deterministic fallback produces empty sections because `_deterministic_diligence_synthesis` (synthesizer.py:2649) groups sources by `source.intent_domain`, but no production code path ever sets this field. Therefore all 25 sources fall into the "other" bucket and every domain section reads "No sources found." The field was added in commit bb7231d but was only populated in test fixtures — the search loop at deep_research_service.py:900-958 never stamps it.

The fix requires threading domain labels through three layers, because the domain knowledge originates in `decompose_diligence_query` (which creates the intents) but must reach the `Source` objects (which are created by `aggregate_sources` downstream). Per the existing dataflow: intents → variants → aggregate → score → merge, the natural place to stamp is after scoring per intent, because at that point we still know which intent produced each source. After the cross-intent dedup at line 961, that association is lost. Therefore:

1. `SearchIntent` needs a `domain` field to carry the label from decomposition to the search loop
2. `decompose_diligence_query` must tag each intent with its domain
3. The search loop must stamp `source.intent_domain` from `intent.domain` before merging

**Docs consulted:** `engine/query_refiner.py:19-24` (SearchIntent dataclass), `engine/deep_research_service.py:900-958` (search loop), `workflows/deep_research/synthesizer.py:2635-2649` (_DILIGENCE_DOMAIN_SECTIONS, grouping logic), `~/.zorora/logs/zorora_20260312.log` (real run showing 25 sources, 0 domains).

## Design

### 1. Add `domain` to `SearchIntent` (query_refiner.py:19-24)

```python
@dataclass
class SearchIntent:
    intent_query: str
    parent_query: str
    is_primary: bool = False
    domain: str = ""  # e.g. "commercial", "licensing", "performance"
```

### 2. Tag each intent in `decompose_diligence_query` (query_refiner.py:567-604)

Add `domain=` to each SearchIntent constructor:
- Intent 1: `domain="commercial"`
- Intent 2: `domain="licensing"`
- Intent 3: `domain="environmental"`
- Intent 4: `domain="performance"`
- Intent 5: `domain="counterparty"`
- Intent 6: `domain="asset_specific"`

### 3. Stamp `intent_domain` on sources in search loop (deep_research_service.py ~line 958)

After `_score_and_filter_intent_sources` returns `intent_relevant_sources`, tag each source:

```python
if is_diligence and intent.domain:
    for src in intent_relevant_sources:
        if not src.intent_domain:
            src.intent_domain = intent.domain
```

The `if not src.intent_domain` guard prevents overwriting if a source was already tagged by an earlier intent (dedup can merge sources across intents).

### 4. Update test (tests/test_sep036.py)

Add a test `test_diligence_sources_tagged_with_intent_domain` that:
- Mocks `aggregate_sources` to return distinct sources per call
- Runs `run_deep_research` with `research_type="diligence"`
- Patches `synthesize_direct` to capture the `ResearchState`
- Asserts that sources in `state.sources_checked` have non-empty `intent_domain`
- Asserts at least 3 distinct domains are present

## Success Criteria

1. Sources retrieved during diligence search have `intent_domain` set to the domain of the intent that found them
2. The deterministic fallback groups sources correctly into domain sections
3. Running the same Lesotho solar diligence query produces a report with populated domain sections, not "No sources found"
4. All existing tests still pass

## Validation

**Verified:**
- `SearchIntent` dataclass at query_refiner.py:19-24 has no `domain` field currently
- `decompose_diligence_query` creates intents without domain tags (query_refiner.py:567-604)
- Search loop at deep_research_service.py:900-958 never sets `intent_domain` on sources
- `_deterministic_diligence_synthesis` groups by `source.intent_domain` (synthesizer.py:2649)
- Real run log confirms 25 sources, 0 domains

**Assumed:**
- Adding `domain=""` default to SearchIntent won't break non-diligence decomposition (all other intents will have empty domain, which is fine)

**Known gaps:**
- If a source appears in multiple intents, only the first intent's domain is kept (acceptable — better than no domain)

## Objective Verification

Run a diligence search for a Lesotho solar asset and verify the deterministic fallback report has populated domain sections with actual source content — not "No sources found for this domain."
