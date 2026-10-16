# Results

**Synthetic only** — these files check the decision logic and the direction front end; they are not real-world measurements.

| File | Produced by | Contents |
|---|---|---|
| `synthetic_results.json` | `python/run_synthetic.py` | Per-seed and mean metrics for baselines A/B, DEDA and ablations; test-stream trade-off curves (Table 4 / Figure 2 of the paper) |
| `synthetic_tradeoff.png` | `python/run_synthetic.py` | False alerts/h and wrong-direction alerts vs missed-or-late rate |
| `acoustic_checks_output.txt` | `python/acoustic_checks.py > ../results/acoustic_checks_output.txt` | Free-field quadrant accuracy, closure, norm and coherence checks (Table 3) |

Recorded-data results will go in `recorded/` once the protocol in `docs/experiment_protocol.md` has been run.
