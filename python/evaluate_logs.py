"""
Baseline comparison on RECORDED trials (offline replay).

Because all three policies consume the same per-window outputs of the
existing DOA + classifier branches, they are compared on IDENTICAL inputs by
replaying logged windows. Only the final, frozen configuration is then run on
the MCU to measure latency/RAM/CPU.

Input files (CSV, header required)
----------------------------------
windows.csv : session,split,t_ms,l_horn,l_siren,l_shout,l_beep,l_ambient,theta,closure,norm,coh
              l_* are RAW classifier logits (temperature is fitted here);
              theta..coh empty when DOA missing.
events.csv  : session,onset_ms,offset_ms,cls,theta,distance_m,noise
              cls in {horn,siren,shout,beep}; ambient-only sessions have no rows.
split       : "calib" (temperature + thresholds) or "test" (reported). Split by
              SESSION and by SOURCE RECORDING - never by window.

Usage
-----
python evaluate_logs.py windows.csv events.csv --target-miss 0.05 --out results.json
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import math
from collections import defaultdict

import numpy as np

from deda.metrics import Event, evaluate
from deda.policy import CLASSES, DEDA, Config, DirObs, FixedThreshold, Window, run


def load(windows_csv, events_csv):
    W = defaultdict(list)
    split = {}
    for r in csv.DictReader(open(windows_csv)):
        logits = np.array([float(r[f"l_{c}"]) for c in CLASSES])
        d = None
        if r["theta"] not in ("", None):
            d = DirObs(float(r["theta"]), float(r["closure"]), float(r["norm"]), float(r["coh"]))
        W[r["session"]].append((float(r["t_ms"]), logits, d))
        split[r["session"]] = r["split"]
    E = defaultdict(list)
    for r in csv.DictReader(open(events_csv)):
        th = float(r["theta"]) if r["theta"] else None
        E[r["session"]].append(Event(float(r["onset_ms"]), float(r["offset_ms"]),
                                     CLASSES.index(r["cls"]), th))
    return W, E, split


def softmax_T(z, T):
    z = z / T
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def fit_temperature(W, E, sessions):
    """Temperature scaling (Guo et al., 2017) on window-level labels derived
    from events (window inside event -> event class, else ambient)."""
    Z, Y = [], []
    for s in sessions:
        for t, z, _ in W[s]:
            y = 4
            for e in E.get(s, []):
                if e.onset_ms + 200 <= t <= e.offset_ms:   # skip onset ramp
                    y = e.cls
            Z.append(z)
            Y.append(y)
    Z, Y = np.array(Z), np.array(Y)
    best = (1.0, float("inf"))
    for T in np.exp(np.linspace(np.log(0.3), np.log(5.0), 60)):
        p = np.array([softmax_T(z, T) for z in Z])
        nll = -np.mean(np.log(p[np.arange(len(Y)), Y] + 1e-12))
        if nll < best[1]:
            best = (float(T), float(nll))
    return best[0]


def windows_for(W, s, T):
    return [Window(t, softmax_T(z, T).tolist(), d) for t, z, d in W[s]]


def pooled(policy_factory, W, E, sessions, T):
    """Run per session (state reset) and pool counts."""
    per = {}
    for s in sessions:
        ws = windows_for(W, s, T)
        total = ws[-1].t_ms - ws[0].t_ms + 1 if ws else 1
        per[s] = evaluate(run(policy_factory(), ws), E.get(s, []), total)
    return per


def summarise(per):
    keys = ["miss_rate", "miss_or_late_rate", "false_alerts_per_hour", "wrong_dir_per_event",
            "nondir_fraction", "lat_p50_ms", "lat_p95_ms", "macro_f1"]
    out = {}
    rng = np.random.default_rng(0)
    S = list(per)
    for k in keys:
        vals = np.array([per[s][k] for s in S], dtype=float)
        est = float(np.nanmean(vals))
        # cluster bootstrap over sessions (sessions are the independent units)
        boots = [np.nanmean(vals[rng.integers(0, len(S), len(S))]) for _ in range(2000)]
        out[k] = (est, float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("windows")
    ap.add_argument("events")
    ap.add_argument("--target-miss", type=float, default=0.05)
    ap.add_argument("--out", default="results.json")
    a = ap.parse_args()
    W, E, split = load(a.windows, a.events)
    cal = [s for s in W if split[s] == "calib"]
    test = [s for s in W if split[s] == "test"]
    T = fit_temperature(W, E, cal)

    def choose(factory_of, grid):
        best = None
        for g in grid:
            per = pooled(lambda: factory_of(g), W, E, cal, T)
            m = summarise(per)
            if m["miss_or_late_rate"][0] <= a.target_miss:
                if best is None or m["false_alerts_per_hour"][0] < best[1]:
                    best = (g, m["false_alerts_per_hour"][0])
        return best[0] if best else grid[0]

    taus = list(np.arange(0.3, 0.99, 0.02))
    base = Config()
    deda_grid = [(dh, dl) for dh in np.arange(-2, 2.01, 0.25) for dl in np.arange(-2, 2.01, 0.25)]

    def mk_deda(k):
        dh, dl = k
        return DEDA(dataclasses.replace(base, h_hi=tuple(h + dh for h in base.h_hi),
                                        h_lo=tuple(min(h + dl, hh + dh) for h, hh in zip(base.h_lo, base.h_hi)),
                                        h_urgent=tuple(h + dh for h in base.h_urgent)))

    chosen = {
        "A": choose(lambda t: FixedThreshold(t, False), taus),
        "B": choose(lambda t: FixedThreshold(t, True), taus),
        "C_DEDA": choose(mk_deda, deda_grid),
    }
    makers = {"A": lambda: FixedThreshold(chosen["A"], False),
              "B": lambda: FixedThreshold(chosen["B"], True),
              "C_DEDA": lambda: mk_deda(chosen["C_DEDA"])}
    results = {n: summarise(pooled(m, W, E, test, T)) for n, m in makers.items()}
    json.dump({"temperature": T, "operating_points": {k: (list(v) if isinstance(v, tuple) else v)
                                                     for k, v in chosen.items()},
               "test_results_mean_ci95": results}, open(a.out, "w"), indent=1, default=float)
    for n, r in results.items():
        print(n, {k: f"{v[0]:.3f} [{v[1]:.3f},{v[2]:.3f}]" for k, v in r.items()})


if __name__ == "__main__":
    main()
