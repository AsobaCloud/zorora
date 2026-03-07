# Polymarket Analytic Report

## Generation Path
Deterministic fallback was used because endpoint generation failed: `missing HF token`

## Executive Summary
- Markets evaluated: 35
- High-signal contracts (score >= 10): 7
- Medium-signal contracts (1 <= score < 10): 5
- This output is a deterministic template summary and should be treated as triage, not final attribution.

## Strongest Signal Contracts
| Score | Market ID | Closed Time | Question |
|---:|---|---|---|
| 41.1911 | 532742 | 2025-06-13 03:24:45+00 | Israel military action against Iran before July? |
| 31.9287 | 532741 | 2025-06-22 03:03:06+00 | US military action against Iran before July? |
| 27.1250 | 531897 | 2025-03-29 23:25:40+00 | Emmers vs. Miranda |
| 16.8900 | 532762 | 2025-04-01 01:10:15+00 | Will Trump say "Iran" during Executive Order signing today? |
| 14.7900 | 534857 | 2025-04-07 21:54:17+00 | Will Trump say "Iran" 3+ times during Netanyahu events today? |
| 12.3900 | 535819 | 2025-04-10 21:04:21+00 | Will Trump say "Iran" 3+ times during his cabinet meeting on April 10? |
| 10.3900 | 535981 | 2025-04-11 20:26:21+00 | Will Karoline Leavitt say "Iran" 3+ times during next White House press briefing? |
| 9.9900 | 521790 | 2025-02-05 02:22:23+00 | Will Trump say "Iran" during his February 4 press conference with Netanyahu? |
| 9.7900 | 531640 | 2025-03-28 03:45:10+00 | Will Trump say "Iran" during today's Iftar Dinner? |
| 8.0900 | 524357 | 2025-02-25 22:35:40+00 | Will Karoline Leavitt say "Iran" during next White House press briefing? |

## Cluster: Iran Strikes
- `532742` score=41.1911 z=28.132163438910418 jump24to1=0.5745 :: Israel military action against Iran before July?
- `532741` score=31.9287 z=10.437418018235103 jump24to1=0.5710000000000001 :: US military action against Iran before July?
- `531897` score=27.1250 z=None jump24to1=0.5245000000000001 :: Emmers vs. Miranda
- `532762` score=16.8900 z=None jump24to1=None :: Will Trump say "Iran" during Executive Order signing today?
- `534857` score=14.7900 z=None jump24to1=None :: Will Trump say "Iran" 3+ times during Netanyahu events today?

## Cluster: Maduro
- `527799` score=0.0100 z=-1.2810343774401616 jump24to1=-0.001 :: Will Nicolás Maduro be the first leader out in 2025?
- `687779` score=0.0000 z=-1.9518352568502777 jump24to1=-0.0015 :: U.S. operation to capture Maduro in 2025?
- `688265` score=0.0000 z=-1.570271559183102 jump24to1=-0.001 :: Maduro in U.S. custody by December 31?
- `1096292` score=0.0000 z=-0.7049639249402475 jump24to1=0.0 :: Nicolás Maduro released from custody by January 9, 2026?

## Cluster: Khamenei
- `1469316` score=0.4800 z=-3.0389244472762384 jump24to1=-0.1145 :: Will Iran name a successor to Khamenei by March 2?
- `1493097` score=0.2600 z=None jump24to1=None :: Will Iran announce a new supreme leader on March 3, 2026?
- `519847` score=0.0500 z=-2.8188069205999287 jump24to1=-0.0015 :: Will Trump meet with Ali Khamenei in his first 100 days?
- `527803` score=0.0000 z=-2.289741489124735 jump24to1=-0.002 :: Will Ali Khamenei be the first leader out in 2025?
- `524150` score=0.0000 z=-0.2958587513919752 jump24to1=-0.0005 :: Will Trump meet with Ali Khamenei in 2025?

## Method Limits
- Price/score anomalies are not legal proof of insider trading.
- Event wording and resolution timing can create mechanical spikes.
- Additional trade-level concentration analysis is required for stronger attribution.

## Next Validation Steps
1. Add wallet concentration metrics for T-6h and T-24h windows.
2. Compare against matched-control markets by topic and liquidity.
3. Cross-check with public-news timestamps and known disclosure windows.