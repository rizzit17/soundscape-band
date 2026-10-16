# Experiment protocol (pre-registered)

Fixed **before** any recorded test data are analysed. Changes after that point must be reported as deviations.

## Primary outcome

**Wrong-direction rate (WDR)** = critical events whose *first* alert drives a motor set that excludes the true quadrant ÷ all critical events.

DEDA succeeds if, relative to Baseline B (fixed threshold + raw angle):

1. WDR is reduced by **≥ 50 %** (relative), and
2. the missed-or-late (> 300 ms) rate is **no more than 2 percentage points worse**, and
3. the 95th-percentile onset-to-vibration latency is **≤ 300 ms**.

## Secondary outcomes

Per-class recall and event-level macro-F1 · false alerts per ambient hour · missed-event rate · four-quadrant direction accuracy · circular angular error |wrap₁₈₀(θ̂ − θ)| · non-directional alert fraction · latency p50/p95 · RAM, flash, CPU per hop · current draw.

Secondary hypotheses:
- **H2** closure, norm and coherence each separate correct- from wrong-quadrant windows (AUROC > 0.7 each).
- **H3** the spatial prior γ lowers false alerts/h at equal missed-or-late rate.
- **H4** the sequential class test (K > 0) lowers false alerts/h at equal missed-or-late rate; if not, set K = 0 and report it.

## Design

**Record once, replay many.** Wear the band on a person or head-and-torso mannequin, record raw synchronous 3-channel audio, and log per-window Path A/B outputs with the same fixed-point code as the MCU. All policies are compared offline on identical inputs ([`python/evaluate_logs.py`](../python/evaluate_logs.py)). The final frozen configuration is then run live to measure latency and resources.

| Factor | Levels |
|---|---|
| Class | horn, siren/alarm, shout, reversing beep |
| Angle | 0°, 90°, 180°, 270° ([layout](figures/test_setup.png)) |
| Radius | 1 m, 3 m, 5 m |
| Noise | quiet; babble; traffic recording (measure SPL at the wearer) |
| Repetitions | 3, each with a different source clip |

→ 4 × 4 × 3 × 3 × 3 = **432 critical trials**.

Plus:
- **≥ 3 h ambient-only audio** from ≥ 3 environments (canteen, roadside, lab with music/TV) for false alerts/h.
- **Challenge sets** (reported separately): two simultaneous sources at different angles; a source moved along an arc; wearer turning 90° mid-event; impulses (door slam, clap, dropped object); horn bursts < 300 ms; siren-like music.

## Splits

- Classifier training data never overlap with evaluation recordings.
- Evaluation recordings are split by **session and source clip** into `calib` (temperature, thresholds, ρ/e/ν limits) and `test` (touched once). Never split by window.

## Latency measurement

Reference microphone at the speaker + accelerometer on each motor, on one multichannel recorder (or GPIO timestamps on a logic analyser). Latency = motor acceleration onset − acoustic onset.

## Statistics

- Proportions: Wilson 95 % CIs. Paired policy comparisons on the same events: McNemar's test.
- False-alert rates: Poisson rates and rate ratio.
- Latency p50/p95 and all metrics: cluster bootstrap over sessions (2,000 resamples).
- Sample size: with discordant share p_d ≈ 0.14 and paired difference δ ≈ 0.12 (assumed 20 % vs 8 % WDR), n ≈ (1.96√p_d + 0.84√(p_d − δ²))² / δ² ≈ 75 events for 80 % power at α = 0.05. Replace the assumed rates with pilot data from 1–2 sessions.
- Report every pre-registered metric, including those where DEDA loses.

## Results tables (to be filled)

**R1 — Main comparison (test split)**

| Policy | WDR % [95 % CI] | Missed % | Missed-or-late % | False alerts/h | Macro-F1 | Latency p50/p95 (ms) |
|---|---|---|---|---|---|---|
| A: classifier only | — | | | | | |
| B: fixed fusion | | | | | | |
| C: DEDA | | | | | | |

**R2 — Ablations**

| Variant | WDR % | Missed-or-late % | False alerts/h | p95 latency (ms) |
|---|---|---|---|---|
| DEDA (full) | | | | |
| no reliability checks | | | | |
| K = 0 | | | | |
| no wait for direction | | | | |
| no non-directional fallback | | | | |
| + spatial prior γ | | | | |

**R3 — On-device resources**

| Platform | Flash (KB) | RAM (KB) | MFCC+CNN/hop (ms) | GCC/hop (ms) | DEDA/hop (µs) | Current (mA) |
|---|---|---|---|---|---|---|
| RP2040 | | | | | | |
| ESP32 | | | | | | |
