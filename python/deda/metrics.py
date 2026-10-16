"""
Event-level evaluation shared by ALL policies (baselines A, B and DEDA).

Works identically on synthetic streams and on per-window logs exported from
recorded trials (see evaluate_logs.py). Ground truth = list of Event.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from .policy import CRITICAL, CLASSES, Alert, quadrant_of


@dataclass
class Event:
    onset_ms: float
    offset_ms: float
    cls: int                    # index into CLASSES; AMBIENT events are not alerts targets
    theta: Optional[float]      # true azimuth (deg, clockwise from front) or None


def _quad_bit(theta: float) -> int:
    return 1 << quadrant_of(theta)


def evaluate(alerts: Sequence[Alert], events: Sequence[Event], total_ms: float,
             deadline_ms: float = 300.0, grace_ms: float = 500.0) -> Dict:
    """Matching rule (pre-registered):
    * An alert is ASSOCIATED with a critical event if onset <= t <= offset+grace.
    * The FIRST associated alert gives the event's detection latency and class.
    * Alerts not associated with any critical event are FALSE ALERTS.
    * UPDATE alerts are reported separately and never count as detections.
    """
    crit = [e for e in events if e.cls in CRITICAL]
    first: List[Optional[Alert]] = [None] * len(crit)
    n_false = 0
    wrong_dir = dir_alerts_on_events = nondir_on_events = 0
    updates = 0
    for a in sorted(alerts, key=lambda a: a.t_ms):
        if a.kind == "UPDATE":
            updates += 1
            continue
        hit = None
        for i, e in enumerate(crit):
            if e.onset_ms <= a.t_ms <= e.offset_ms + grace_ms:
                hit = i
                break
        if hit is None:
            n_false += 1
            continue
        if first[hit] is None:
            first[hit] = a
            e = crit[hit]
            if a.kind == "DIR" and e.theta is not None:
                dir_alerts_on_events += 1
                if not (a.motors & _quad_bit(e.theta)):
                    wrong_dir += 1
            elif a.kind == "NONDIR":
                nondir_on_events += 1
        # additional alerts during the same event are neither TP nor FP
    # per-class recall (detected with the CORRECT class, any latency)
    per_class = {}
    for c in CRITICAL:
        idx = [i for i, e in enumerate(crit) if e.cls == c]
        if idx:
            per_class[CLASSES[c]] = sum(first[i] is not None and first[i].cls == c
                                        for i in idx) / len(idx)
    lat = np.array([first[i].t_ms - crit[i].onset_ms for i in range(len(crit))
                    if first[i] is not None])
    detected = sum(f is not None for f in first)
    in_time = int(np.sum(lat <= deadline_ms)) if len(lat) else 0
    # macro-F1 over critical classes (event-level)
    f1s = []
    for c in CRITICAL:
        tp = sum(1 for i, e in enumerate(crit) if e.cls == c and first[i] is not None and first[i].cls == c)
        fn = sum(1 for e in crit if e.cls == c) - tp
        fp_c = sum(1 for i, e in enumerate(crit) if first[i] is not None and first[i].cls == c and e.cls != c)
        fp_c += sum(1 for a in alerts if a.kind != "UPDATE" and a.cls == c and
                    not any(e.onset_ms <= a.t_ms <= e.offset_ms + grace_ms for e in crit))
        if tp + fn == 0:
            continue
        p = tp / (tp + fp_c) if tp + fp_c else 0.0
        r = tp / (tp + fn)
        f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    crit_ms = sum(e.offset_ms - e.onset_ms + grace_ms for e in crit)
    amb_hours = max(total_ms - crit_ms, 1.0) / 3.6e6
    return {
        "n_events": len(crit),
        "miss_rate": 1 - detected / len(crit) if crit else float("nan"),
        "miss_or_late_rate": 1 - in_time / len(crit) if crit else float("nan"),
        "per_class_recall": per_class,
        "macro_f1": float(np.mean(f1s)) if f1s else float("nan"),
        "false_alerts_per_hour": n_false / amb_hours,
        "n_false": n_false,
        "wrong_dir_rate": wrong_dir / dir_alerts_on_events if dir_alerts_on_events else float("nan"),
        "wrong_dir_per_event": wrong_dir / len(crit) if crit else float("nan"),
        "nondir_fraction": nondir_on_events / detected if detected else float("nan"),
        "lat_p50_ms": float(np.percentile(lat, 50)) if len(lat) else float("nan"),
        "lat_p95_ms": float(np.percentile(lat, 95)) if len(lat) else float("nan"),
        "updates": updates,
    }


def wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)
