# Polymarket Analytic Report

## What This Report Tests
This report tests whether anomaly signals in completed Polymarket contracts can separate likely leak-like pre-resolution patterns from background noise across Iran-strike, Maduro, and Khamenei-related markets.

## Data Scope
- Platform: Polymarket
- Time window: 2025-01-01T00:00:00Z to 2026-12-31T23:59:59Z
- Markets evaluated: 35
- High-confidence candidates: 2
- Supporting (weaker) candidates: 2
- Likely noise / excluded: 31
- Generation mode: deterministic fallback (`model output failed report validation on root endpoint`)

## How Score Works
- Composite score = 0.50 * max_6h_z + 0.30 * (jump_24h_to_1h * 100) + 0.20 * (range_6h * 100).
- `max_6h_z` measures late-window deviation from baseline volatility.
- `jump_24h_to_1h` measures directional move into close.
- `range_6h` measures the size of late-window movement.
- This score is an anomaly heuristic, not a calibrated probability of event occurrence.

## Key Findings
- Highest-ranked markets are concentrated in Iran strike-timing contracts.
- Top high-confidence market IDs:
- `532742` score=41.1911, z=28.132, jump24to1=0.5745 :: Israel military action against Iran before July?
- `532741` score=31.9287, z=10.437, jump24to1=0.5710 :: US military action against Iran before July?
- Cluster diagnostics:
- Iran Strikes: top market `532742` score=41.1911 (Israel military action against Iran before July?)
- Maduro: top market `527799` score=0.0100 (Will Nicolás Maduro be the first leader out in 2025?)
- Khamenei: top market `1469316` score=0.4800 (Will Iran name a successor to Khamenei by March 2?)
- Likely-noise examples:
- `532762` score=16.8900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" during Executive Order signing today?
- `534857` score=14.7900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" 3+ times during Netanyahu events today?
- `535819` score=12.3900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" 3+ times during his cabinet meeting on April 10?
- `535981` score=10.3900, z=n/a, jump24to1=n/a :: Will Karoline Leavitt say "Iran" 3+ times during next White House press briefing?
- `521790` score=9.9900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" during his February 4 press conference with Netanyahu?

## What This Means
Hypothesis verdict: partial support. The strongest anomaly signal appears in Iran strike-timing markets, while Maduro and Khamenei clusters do not show comparable strength in this run.
In this run, the signal-vs-noise separation is meaningful for a narrow slice of Iran strike-timing markets, but not yet replicated across Maduro and Khamenei cases.

## What This Does Not Prove
- It does not prove insider trading or illegal conduct.
- It does not identify traders, intent, or information sources.
- It does not establish causal linkage to classified information without external corroboration.

## Next Validation Steps
1. Align each spike with first public-news timestamps to test lead-lag behavior.
2. Add wallet concentration metrics (top-wallet share, HHI) in T-24h and T-6h windows.
3. Run matched controls by topic, horizon, and liquidity to estimate false-positive rate.
