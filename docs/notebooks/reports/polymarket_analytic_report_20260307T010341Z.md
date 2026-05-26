# Can Sudden Prediction-Market Spikes Reliably Signal Real Events?

## Abstract
This study tests whether abrupt, last-minute price spikes in prediction markets can be used as a reliable early-warning signal of real-world events, rather than treated as ordinary market noise. We analyzed 35 closed Polymarket contracts from January 1, 2025 through December 31, 2026. The experiment compared a seeded case set of 10 contracts tied to known suspicious contexts (Iran strike-timing, Maduro, and Khamenei succession) against a broader non-seeded comparator pool from the same dataset, including a stricter event-eligible control subset of 17 markets after removing speech/process contracts. The strongest anomalies were concentrated in two Iran strike-timing contracts, while Maduro and Khamenei clusters remained weak. The result is partial support for the hypothesis: there is a meaningful signal architecture in a narrow contract class, but not yet broad repeatability across all targeted geopolitical categories.

## Research Question
Can sudden pre-event spikes in prediction-market prices function as repeatable warning signals of meaningful real-world events?

## Data
The dataset contains 35 closed Polymarket markets in the 2025–2026 window. We defined a seeded case group of 10 contracts linked to the three target clusters (Iran strike-timing, Maduro, Khamenei). The non-seeded comparator group contains 25 contracts from the same pulled set. To reduce obvious structural noise, we also evaluated an event-eligible non-seeded control subset of 17 contracts after filtering speech/process-style markets.

This is a case-versus-comparator design within the same pulled dataset. It is not yet a full random sample of the global market universe, so baseline false-positive estimates remain provisional.

## Method
For each market, we computed a late-window anomaly score from three features near close: abnormal volatility (`max_6h_z`), directional acceleration into close (`jump_24h_to_1h`), and six-hour range (`range_6h`). The composite score is:

`0.50*max_6h_z + 0.30*(jump_24h_to_1h*100) + 0.20*(range_6h*100)`

The score is a screening heuristic for unusual timing behavior; it is not a calibrated probability that an event will occur.

## Results
Against event-eligible controls, the seeded set shows materially stronger anomaly behavior. Seeded markets have a mean score of 7.5989 versus 1.7052 for controls (delta +5.8937). At the higher-signal thresholds, 20.00% of seeded markets score at least 10, compared with 5.88% of controls; at 20+, seeded remains 20.00% versus 5.88% for controls.

The top two seeded contracts are both Iran strike-timing markets: `532742` (41.1911) and `532741` (31.9287). By contrast, the top Maduro and Khamenei seeded contracts are weak (`527799`: 0.0100; `1469316`: 0.4800). This indicates concentration of signal strength in one cluster rather than broad cross-cluster consistency.

Non-seeded outliers do exist (for example `531897`, score 27.1250), which reinforces that high scores alone are not enough; context and market type still matter.

## Interpretation
The findings support a narrow version of the hypothesis. In this run, sudden spike behavior appears informative in a specific subset of Iran strike-timing contracts, but the same strength does not replicate across Maduro and Khamenei contracts. In operational terms, this is better understood as a focused anomaly detector than a universal geopolitical forecasting engine.

## Conclusion
The study provides partial evidence that pre-event price spikes in prediction markets can carry actionable signal, but only in a constrained slice of contracts. The current evidence does not support broad deployment across all event types. Immediate utility is highest when used as a targeted alerting layer for high-risk strike-timing markets, followed by deeper investigation.

## So What
For decision-making, this framework is useful now as a trigger system: when specific high-risk contracts show abrupt late-window acceleration, analysts should escalate review. It should not yet be treated as a standalone predictor across the full market.

The next step to make this publication-grade is straightforward: rerun the same scoring pipeline on a true random baseline of closed markets and quantify false-positive rates under identical thresholds.
