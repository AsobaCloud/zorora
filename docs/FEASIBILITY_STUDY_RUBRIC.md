# How to use feasibility studies (Scouting)

This guide is for **people reviewing sites** in Zorora’s Scouting workflow—not for engineers. Use it to understand what each study is telling you, how much to trust it, and what to do next.

---

## What you’re looking at

Feasibility studies are **five quick, focused checks** on a site that is already on your kanban in the **Feasibility** stage. Each check answers one plain question. Together they give a **directional** read (“does this deserve deeper work?”)—not a bankable model, not a guarantee.

**Important:** Verdicts are produced by an AI analyst after the system feeds it **real local data** (prices, grid zones, resource numbers, regulatory headlines, etc.). The AI still **interprets** that bundle. Treat outputs as **structured expert-style notes**, not signed-off engineering or legal advice.

---

## The five studies (what to use each one for)

### 1. Production — “Will the resource side look credible?”

**Question it targets:** Is there enough sun, wind, or comparable build-out in the area to make generation plausible?

**What goes in:** Your site’s location, technology, and size, plus satellite-style resource stats and a snapshot of similar plants in the same country (where data exists).

**Use it when:** You want a sanity check before worrying about markets or finance.

---

### 2. Trading — “Can we plausibly make money from market / tariff shapes?”

**Question it targets:** Do day-ahead price patterns and (where relevant) tariff data suggest there’s something to capture—arbitrage, spreads, time-of-use value?

**What goes in:** Southern Africa day-ahead market data mapped to a pricing **node** near your site (South Africa is split north/south by latitude; Zimbabwe has its own node). Eskom time-of-use tariff coverage is summarized when available.

**You may see a chart:** Average **price through the day** (USD per MWh). Use it to see whether the profile is flat, peaky, or shaped in a way that matters for your technology.

**Use it when:** You care about merchant or hybrid revenue stories, or BESS-style arbitrage.

---

### 3. Grid — “Is there a plausible hook-in point?”

**Question it targets:** How far is the site from the **nearest** major transmission / MTS-style zone center in the GCCA grid layer, and what’s it called?

**What goes in:** Distance from your pin to the nearest zone centroid in the loaded grid dataset—not a full interconnection study.

**Use it when:** You need a first-pass “are we in the middle of nowhere or near backbone infrastructure?”

**Caveat:** Nearest-substation distance is **not** spare capacity, queue, or energization date. Treat grid as **directional proximity**, not permission to connect.

---

### 4. Regulatory — “Does the local filing environment look busy or empty?”

**Question it targets:** Are there recent regulatory events in the jurisdiction that suggest an active licensing / policy environment?

**What goes in:** Recent items from the app’s regulatory event store that match the site’s country (when the store has data).

**Use it when:** You want a **pulse check**, not a legal memo.

**Caveat:** “No events found” often means **no data in the database**, not “no rules apply.”

---

### 5. Financial — “Given the other four, does the story hang together?”

**Question it targets:** If you squint at production, trading, grid, and regulatory together—plus a bit of macro (e.g. exchange rate when available)—does the case still look worth pursuing?

**What goes in:** Summaries of **whatever other tabs you’ve already run** for this same site, plus light macro context when the system has it.

**Use it when:** You’re ready to synthesize—not as the first click.

**Strong recommendation:** Run **Production, Trading, Grid, and Regulatory first**. The tool is built so the financial read is **more honest** when several of those exist; if you run Financial alone or too early, expect **lower stated confidence** by design.

---

## How to read every study (same layout)

Each tab is structured the same way so you can scan quickly:

| Piece | What it means for you |
|--------|------------------------|
| **Key finding** | The one sentence to remember from that dimension. |
| **Conclusion** | **Favorable** — tailwinds dominate for this dimension. **Marginal** — mixed or unclear. **Unfavorable** — headwinds dominate. |
| **Confidence** | **High** — the system had enough relevant data and the story is relatively tight. **Medium** — usable but incomplete. **Low** — thin data, conflicting signals, or you skipped tabs the Financial view wanted. |
| **Risks** | Specific things that could invalidate the optimistic read. |
| **Gaps** | What’s missing, assumed, or needs a human or vendor to fill in. |

If the model fails or returns garbled text, you may see **Marginal** / **Medium** with a generic fallback line—treat that as “**rerun or ignore until fixed**,” not a real judgment.

---

## Practical workflow (recommended)

1. Move the card to **Feasibility** when you’re ready for structured pre-diligence.
2. Run **Production** and **Grid** first if the site is new to you (resource + wires).
3. Run **Trading** if revenue shape matters for the thesis.
4. Run **Regulatory** for a jurisdiction temperature check.
5. Run **Financial last** to synthesize—and revisit Financial if you change any of the other tabs materially.

**Progress:** The UI shows how many of the five you’ve completed (e.g. “3/5”). Use that as a nudge, not a score.

---

## When to trust it—and when to escalate

**Reasonable to rely on for:** Prioritization, internal memos, conversation starters with developers or lenders, deciding whether to commission real studies.

**Not a substitute for:** Interconnection applications, PPA negotiation, environmental permits, tax structuring, or investment committee sign-off.

**Escalate to full diligence / external advisors when:** Any tab is **Unfavorable** with **High** confidence, **Financial** stays **Marginal** or **Unfavorable** after all four precursors are done, or **Gaps** list items that are deal-breakers (e.g. land rights, grid capacity, offtake).

---

## Connection to Deep Research

After feasibility work is saved, relevant studies can surface as **internal context** when you run **Deep Research** on related topics (for items that have moved far enough along the Scouting path). That helps new questions reuse what you already learned—still verify anything critical.

---

## Where the behavior is defined (optional)

If you need implementation detail, the logic lives in `workflows/feasibility.py` in the repository. Original product intent for the five tabs is summarized in `.sep/SEP-045.md`.
