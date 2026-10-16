"""
SYNTHETIC comparison of A / B / DEDA and ablations.

Protocol (mirrors the real-data protocol in the report):
  1. Generate a CALIBRATION stream (seed s) and a TEST stream (seed s+1000).
  2. For each policy, sweep one operating-point knob on the calibration
     stream and keep the setting with the fewest false alerts/hour subject to
     miss-or-late rate <= TARGET.
  3. Report test-stream metrics at that frozen setting.
Repeated over several seeds; mean and min/max are printed.

These numbers exercise the logic only; they are NOT evidence of real-world
performance (the generator's parameters are assumptions).
"""
from __future__ import annotations

import dataclasses
import json
import sys

import os

import numpy as np

from deda.metrics import evaluate
from deda.policy import DEDA, Config, FixedThreshold, run
from deda.synth import SynthParams, generate

TARGET = 0.10   # max miss-or-late rate on calibration stream
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
SEEDS = [1, 2, 3, 4]
DUR = 1200.0


def deda_factory(**flags):
    """Two knobs: offset of the immediate threshold h_hi and of the deadline
    floor h_lo (h_urgent moves with h_hi). Same offsets for every class."""
    def make(knob):
        d_hi, d_lo = knob
        base = Config(**flags)
        return DEDA(dataclasses.replace(
            base,
            h_hi=tuple(h + d_hi for h in base.h_hi),
            h_lo=tuple(min(h + d_lo, hh + d_hi) for h, hh in zip(base.h_lo, base.h_hi)),
            h_urgent=tuple(h + d_hi for h in base.h_urgent)))
    grid = [(a, b) for a in np.arange(-2.5, 3.01, 0.5) for b in np.arange(-3.0, 2.01, 0.5)]
    return make, grid


POLICIES = {
    "A_classifier_only": (lambda tau: FixedThreshold(tau, use_direction=False), np.arange(0.40, 0.991, 0.025)),
    "B_fixed_fusion": (lambda tau: FixedThreshold(tau, use_direction=True), np.arange(0.40, 0.991, 0.025)),
    "C_DEDA": deda_factory(),
    "abl_no_dir_reliability": deda_factory(use_dir_reliability=False),
    "abl_no_sequential(K=0)": deda_factory(sequential=False),
    "abl_no_fallback(STRGF-gate)": deda_factory(fallback_nondir=False),
    "abl_no_dir_wait": deda_factory(wait_for_dir=False),
    "ext_gamma_spatial=0.75": deda_factory(gamma_spatial=0.75),
}

KEYS = ["miss_rate", "miss_or_late_rate", "false_alerts_per_hour", "wrong_dir_rate",
        "wrong_dir_per_event", "nondir_fraction", "macro_f1", "lat_p50_ms", "lat_p95_ms"]


def pick(make, grid, cal):
    w, e, T = cal
    best = None
    for g in grid:
        m = evaluate(run(make(g), w), e, T)
        if m["miss_or_late_rate"] <= TARGET:
            if best is None or m["false_alerts_per_hour"] < best[1]:
                best = (g, m["false_alerts_per_hour"])
    if best is None:  # cannot meet target: take the most sensitive setting
        best = (grid[0], None)
    return best[0]


def pareto(make, grid, tests):
    """Test-stream trade-off: for every knob value, pooled (miss-or-late, FA/h)."""
    pts = []
    for g in grid:
        ms = [evaluate(run(make(g), w), e, T) for (w, e, T) in tests]
        pts.append((float(np.mean([m["miss_or_late_rate"] for m in ms])),
                    float(np.mean([m["false_alerts_per_hour"] for m in ms])),
                    float(np.nanmean([m["wrong_dir_per_event"] for m in ms]))))
    pts.sort()
    front, best = [], float("inf")
    for p in pts:
        if p[1] < best:
            front.append(p)
            best = p[1]
    return front


def main():
    sp = SynthParams(duration_s=DUR)
    res = {k: [] for k in POLICIES}
    for s in SEEDS:
        cal, test = generate(sp, s), generate(sp, s + 1000)
        for name, (make, grid) in POLICIES.items():
            g = pick(make, grid, cal)
            m = evaluate(run(make(g), test[0]), test[1], test[2])
            m["knob"] = g
            res[name].append(m)
    print(f"SYNTHETIC ONLY | {len(SEEDS)} seeds x {DUR/60:.0f} min test streams | "
          f"operating point: miss-or-late <= {TARGET:.0%} on calibration stream\n")
    hdr = f"{'policy':30s}" + "".join(f"{k[:14]:>15s}" for k in KEYS)
    print(hdr)
    summary = {}
    for name, ms in res.items():
        row = {k: float(np.nanmean([m[k] for m in ms])) for k in KEYS}
        summary[name] = row
        print(f"{name:30s}" + "".join(f"{row[k]:15.3f}" for k in KEYS))
    # trade-off curves on the test streams
    tests = [generate(sp, s + 1000) for s in SEEDS]
    fronts = {n: pareto(mk, gr, tests) for n, (mk, gr) in POLICIES.items()
              if n in ("B_fixed_fusion", "C_DEDA", "abl_no_sequential(K=0)", "abl_no_dir_wait",
                       "ext_gamma_spatial=0.75")}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
        for n, fr in fronts.items():
            ax.plot([p[0] * 100 for p in fr], [p[1] for p in fr], marker="o", ms=3, label=n)
            ax2.plot([p[0] * 100 for p in fr], [p[2] * 100 for p in fr], marker="o", ms=3, label=n)
        ax.set_xlabel("missed-or-late (>300 ms) critical events, %")
        ax.set_ylabel("false alerts per ambient hour")
        ax.set_yscale("log")
        ax2.set_xlabel("missed-or-late (>300 ms) critical events, %")
        ax2.set_ylabel("wrong-direction alerts, % of critical events")
        fig.suptitle("SYNTHETIC decision streams only - logic check, not evidence")
        for a in (ax, ax2):
            a.grid(alpha=.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS, "synthetic_tradeoff.png"), dpi=150)
    except ImportError:
        pass
    json.dump({"note": "SYNTHETIC decision-level streams; not real-world evidence",
               "per_seed": res, "mean": summary, "pareto_test": fronts}, open(os.path.join(RESULTS, "synthetic_results.json"), "w"),
              indent=1, default=float)


if __name__ == "__main__":
    sys.exit(main())
