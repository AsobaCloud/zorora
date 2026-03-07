# Polymarket Analytic Report

## What This Report Tests
This report tests whether completed Polymarket contracts in 2025-2026 show pre-resolution price patterns consistent with potential information leakage signals.

## Data Scope
- Platform: Polymarket
- Time window: 2025-01-01T00:00:00Z to 2026-12-31T23:59:59Z
- Markets evaluated: 35
- Event clusters: Iran strikes, Maduro-related, Khamenei-related
- Generation mode: deterministic fallback (`missing HF token`)

## How Score Works
- Composite score = 0.50 * max_6h_z + 0.30 * (jump_24h_to_1h * 100) + 0.20 * (range_6h * 100).
- `max_6h_z` measures late-window deviation from baseline volatility.
- `jump_24h_to_1h` measures the directional move into close.
- `range_6h` measures the magnitude of late-window movement.

## Key Findings
- High-confidence signals: 2
- Supporting but weaker signals: 2
- Likely noise / excluded contracts: 31

High-Confidence Signals
- `532742` score=41.1911, z=28.132, jump24to1=0.5745 :: Israel military action against Iran before July?
- `532741` score=31.9287, z=10.437, jump24to1=0.5710 :: US military action against Iran before July?

Likely Noise / Excluded
- `532762` score=16.8900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" during Executive Order signing today?
- `534857` score=14.7900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" 3+ times during Netanyahu events today?
- `535819` score=12.3900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" 3+ times during his cabinet meeting on April 10?
- `535981` score=10.3900, z=n/a, jump24to1=n/a :: Will Karoline Leavitt say "Iran" 3+ times during next White House press briefing?
- `521790` score=9.9900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" during his February 4 press conference with Netanyahu?
- `531640` score=9.7900, z=n/a, jump24to1=n/a :: Will Trump say "Iran" during today's Iftar Dinner?
- `524357` score=8.0900, z=-0.270, jump24to1=-0.3445 :: Will Karoline Leavitt say "Iran" during next White House press briefing?
- `539681` score=1.2139, z=1.938, jump24to1=0.0065 :: Nothing Ever Happens: May

Cluster Snapshot
- Iran Strikes: top score 41.1911 on `532742` (Israel military action against Iran before July?)
- Maduro: top score 0.0100 on `527799` (Will Nicolás Maduro be the first leader out in 2025?)
- Khamenei: top score 0.4800 on `1469316` (Will Iran name a successor to Khamenei by March 2?)

## What This Means
The strongest evidence in this run is concentrated in specific Iran strike-timing contracts, while Maduro and Khamenei clusters are weaker in score and/or direction.

## What This Does Not Prove
- It does not prove insider trading or illegal conduct.
- It does not identify who traded or why they traded.
- It does not control for all market-structure and resolution-rule effects.

## Next Validation Steps
1. Add wallet concentration metrics (top-wallet share, HHI) in T-24h and T-6h windows.
2. Run matched-control comparisons by topic, time horizon, and liquidity decile.
3. Map spikes against external public-news timestamps and known disclosure windows.