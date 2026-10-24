"""Run the connected acoustic stress suite and save new, timestamped results."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from deda.simulator import experiment
from simulator_server import csv_result


def save_results(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "experiment.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    (directory / "trials.csv").write_text(csv_result(result), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    metrics = [("wrong_direction_pct", "Wrong-direction alerts\n% of critical events"),
               ("missed_or_late_pct", "Missed or late\n% of critical events"),
               ("nondirectional_pct", "General first warnings\n% of detected events")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 4))
    for ax, (key, label) in zip(axes, metrics):
        values = [result["policies"][p][key] for p in ("baseline", "deda")]
        ax.bar(["Baseline B", "DEDA"], [v if v is not None else 0 for v in values], color=["#a1b09c", "#497954"])
        ax.set_ylim(0, 105)
        ax.set_title(label, fontsize=10)
        for i, v in enumerate(values):
            ax.text(i, (v or 0) + 2, f"{v:.1f}%" if v is not None else "N/A", ha="center", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("SoundScape acoustic stress suite | synthetic class inputs | default thresholds", fontsize=11)
    fig.text(.5, .02, "New simulation results; separate from the paper benchmark. Not hardware or trained-classifier performance.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .06, 1, .92))
    fig.savefig(directory / "comparison.png", dpi=180)
    plt.close(fig)
    (directory / "README.txt").write_text(result["note"] + "\n\n" + json.dumps(result["policies"], indent=2), encoding="utf-8")
    return directory


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", choices=("quick", "full"), default="quick")
    ap.add_argument("--seeds", type=int, choices=range(1, 6), default=2)
    ap.add_argument("--out", type=Path, help="New output directory; defaults to results/simulation/<UTC timestamp>")
    args = ap.parse_args()
    directory = args.out or Path(__file__).resolve().parents[1] / "results" / "simulation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if directory.exists() and any(directory.iterdir()):
        ap.error("Output directory is not empty; choose a new directory to preserve earlier runs")
    print(f"Running {args.suite} suite with {args.seeds} seed(s)…", flush=True)
    result = experiment({"suite": args.suite, "seeds": args.seeds})
    save_results(result, directory)
    print(json.dumps(result["policies"], indent=2))
    print(f"Saved JSON, CSV, graph and notes to {directory}")


if __name__ == "__main__":
    main()
