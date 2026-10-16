"""Writes windows.csv/events.csv in the evaluate_logs.py format from the
SYNTHETIC generator - only to smoke-test the evaluation pipeline."""
import csv, math, sys
from deda.synth import SynthParams, generate
from deda.policy import CLASSES

def main(prefix="demo"):
    sp = SynthParams(duration_s=300)
    with open(f"{prefix}_windows.csv", "w", newline="") as fw, open(f"{prefix}_events.csv", "w", newline="") as fe:
        w = csv.writer(fw); e = csv.writer(fe)
        w.writerow(["session", "split", "t_ms"] + [f"l_{c}" for c in CLASSES] + ["theta", "closure", "norm", "coh"])
        e.writerow(["session", "onset_ms", "offset_ms", "cls", "theta", "distance_m", "noise"])
        for s in range(6):
            ws, evs, _ = generate(sp, 100 + s)
            split = "calib" if s < 3 else "test"
            for x in ws:
                d = x.dir
                w.writerow([f"S{s}", split, x.t_ms] + [math.log(max(p, 1e-9)) for p in x.probs] +
                           ([d.theta_deg, d.closure, d.norm, d.coherence] if d else ["", "", "", ""]))
            for ev in evs:
                e.writerow([f"S{s}", ev.onset_ms, ev.offset_ms, CLASSES[ev.cls], ev.theta, [1, 3, 5][ev.dist], "synthetic"])

if __name__ == "__main__":
    main(*sys.argv[1:])
