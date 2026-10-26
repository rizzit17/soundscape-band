"""Connected acoustic/DEDA simulation. Classification remains an explicit input model.

No hardware, trained classifier, room solver or motor dynamics are represented.
Reuses the repository's free-field array, GCC-PHAT and policy implementations.
"""
from __future__ import annotations

import dataclasses
import math
import time
from typing import Any

import numpy as np

from .doa import estimate_direction, simulate_array, triangle_positions
from .policy import CLASSES, Config, DEDA, DirObs, FixedThreshold, Window, dir_valid, quadrant_of

CONDITIONS = ("clean", "interference", "clock_fault", "reflection", "dropout")
MOTOR_NAMES = ((1, "Front"), (2, "Right"), (4, "Back"), (8, "Left"))


def number(value, name, low, high, integer=False):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a number") from None
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    if integer and result != int(result):
        raise ValueError(f"{name} must be an integer")
    return int(result) if integer else result


def options(raw: dict | None = None) -> dict:
    raw = raw or {}
    cls = raw.get("sound", "horn")
    condition = raw.get("condition", "clean")
    if cls not in CLASSES or condition not in CONDITIONS:
        raise ValueError("Unknown sound or acoustic condition")
    return dict(sound=cls, condition=condition,
                angle=number(raw.get("angle", 180), "angle", 0, 359),
                snr_db=number(raw.get("snr_db", 20), "SNR", -25, 30),
                confidence=number(raw.get("confidence", .95), "confidence", .05, .99),
                seed=number(raw.get("seed", 7), "seed", 0, 1_000_000, True),
                active_frac=number(raw.get("active_frac", .25), "active fraction", .25, 1),
                event_ms=number(raw.get("event_ms", 1024), "event duration", 64, 1536, True))


def source_signal(sound, t, rng):
    """Procedural sound surrogates, not recordings or class recognition."""
    if sound == "horn":
        phase = 2 * np.pi * 420 * t
        return sum(np.sin(h * phase + rng.uniform(0, 2 * np.pi)) / h for h in range(1, 12))
    if sound == "siren":
        freq = 1000 + 400 * np.sin(2 * np.pi * 2.5 * t)
        phase = 2 * np.pi * np.cumsum(freq) / 16000
        return np.sin(phase) + .3 * np.sin(2 * phase)
    if sound == "beep":
        return (np.sin(2 * np.pi * 1300 * t) + .25 * np.sin(2 * np.pi * 2600 * t)) * (.5 + .5 * np.cos(2 * np.pi * 5 * t))
    if sound == "shout":
        # A speech-like amplitude-modulated broadband surrogate; no actual speech.
        return rng.normal(size=len(t)) * (.6 + .4 * np.sin(2 * np.pi * 7 * t))
    return np.zeros(len(t))


def alert_dict(a):
    return dict(t_ms=a.t_ms, kind=a.kind, sound=CLASSES[a.cls], cls=a.cls,
                motors=a.motors, motor_names=[n for b, n in MOTOR_NAMES if a.motors & b],
                theta=a.theta, evidence_index=a.k)


def outcome(alerts, o, onset, offset):
    first = next((a for a in alerts if a.kind != "UPDATE" and onset <= a.t_ms <= offset + 500), None)
    critical = o["sound"] != "ambient"
    detections = [a for a in alerts if a.kind != "UPDATE"]
    false = sum(not critical or not onset <= a.t_ms <= offset + 500 for a in detections)
    wrong = bool(critical and first and first.kind == "DIR" and not first.motors & (1 << quadrant_of(o["angle"])))
    return dict(critical=critical, detected=bool(first) if critical else False,
                correct_class=bool(first and CLASSES[first.cls] == o["sound"]) if critical else None,
                missed=critical and first is None,
                missed_or_late=critical and (first is None or first.t_ms - onset > 300),
                wrong_direction=wrong, nondirectional=bool(first and first.kind == "NONDIR") if critical else False,
                latency_ms=first.t_ms - onset if critical and first else None,
                false_alerts=false,
                first_alert=alert_dict(first) if critical and first else None)


def simulate(raw: dict | None = None, *, include_frames=True) -> dict[str, Any]:
    started = time.perf_counter()
    o = options(raw)
    rng = np.random.default_rng(o["seed"])
    fs, hop = 16000, 1024
    onset, offset = 192., 192. + o["event_ms"]
    total_ms = math.ceil((offset + 640) / 64) * 64
    t = np.arange(int(total_ms * fs / 1000)) / fs
    active = (t >= onset / 1000) & (t < offset / 1000)
    src = source_signal(o["sound"], t, rng) * active
    if o["sound"] != "ambient":
        src /= max(float(np.sqrt(np.mean(src[active] ** 2))), 1e-12)
    pos = triangle_positions(.035)
    # Preserve the existing ideal free-field model, then add noise at a defined
    # active-source RMS. Its circular fractional delays are synthetic-only.
    mic_offsets = (0., 0., 3.) if o["condition"] == "clock_fault" else (0., 0., 0.)
    channels = simulate_array(src, o["angle"], pos, fs, 200, rng, mic_offsets)
    if o["condition"] == "interference":
        other = rng.normal(size=len(t)) * active
        channels += simulate_array(other, (o["angle"] + 135) % 360, pos, fs, 200, rng)
    elif o["condition"] == "reflection":
        delay = int(.012 * fs)
        reflected = np.concatenate([np.zeros(delay), src[:-delay]])
        channels += .7 * simulate_array(reflected, (o["angle"] + 120) % 360, pos, fs, 200, rng)
    noise_rms = 10 ** (-o["snr_db"] / 20) if o["sound"] != "ambient" else 1.
    channels += rng.normal(0, noise_rms, channels.shape)

    cfg = Config()
    deda = DEDA(cfg)
    baseline = FixedThreshold(.7, True)
    alerts, baseline_alerts, frames = [], [], []
    for i in range(0, len(t) - hop + 1, hop):
        tm = (i + hop) * 1000 / fs
        frame = channels[:, i:i + hop]
        obs, taus = estimate_direction(frame, fs, pos, active_frac=o["active_frac"])
        d = None if o["condition"] == "dropout" else DirObs(**dataclasses.asdict(obs))
        coverage = float(np.mean(active[i:i + hop]))
        probs = np.full(5, .01)
        if o["sound"] != "ambient" and coverage > 0:
            c = CLASSES.index(o["sound"])
            # Deliberately simulated probabilities; acoustic SNR is not a CNN.
            p = .02 + (o["confidence"] - .02) * coverage
            probs[:] = (1 - p) / 4
            probs[c] = p
        else:
            probs[4] = .96
        w = Window(tm, probs.tolist(), d)
        new = deda.step(w)
        bnew = baseline.step(w)
        alerts.extend(new)
        baseline_alerts.extend(bnew)
        if include_frames:
            reasons = []
            if d is None:
                reasons.append("Direction observation removed by injected dropout")
            else:
                if d.closure > cfg.closure_max: reasons.append("Delay closure exceeds 0.75 samples")
                if not cfg.norm_lo <= d.norm <= cfg.norm_hi: reasons.append("Plane-wave norm outside 0.6–1.4")
                if d.coherence < cfg.rho_min: reasons.append("PHAT coherence below 0.30")
            if new:
                decision = "General warning: accepted class, direction uncertain" if new[0].kind == "NONDIR" else "Direction update" if new[0].kind == "UPDATE" else "Directional warning"
            elif deda.latched is not None:
                decision = "Class accepted; gathering direction evidence"
            elif deda.open:
                decision = "Accumulating class evidence"
            elif deda.sup.tracks:
                decision = "Ongoing event: repeat alert suppressed"
            else:
                decision = "No accepted critical event"
            frames.append(dict(t_ms=tm, source_active=bool(coverage), probs=probs.tolist(),
                               direction=dataclasses.asdict(obs), taus=taus.tolist(),
                               direction_available=d is not None, reliable=dir_valid(d, cfg),
                               reasons=reasons or ["Per-window geometry checks pass; DEDA also checks accumulated direction evidence"],
                               evidence=deda.L.copy(), decision=decision,
                               alerts=[alert_dict(a) for a in new],
                               baseline_alerts=[alert_dict(a) for a in bnew],
                               waveform=frame[:, ::16].tolist()))

    return dict(schema_version=1, note="Synthetic free-field audio; class probabilities are simulated inputs, not a trained classifier. No hardware measurements.",
                options=o, sample_rate=fs, hop_ms=64, onset_ms=onset, offset_ms=offset,
                duration_ms=total_ms, processing_allowance_ms=cfg.proc_ms,
                runtime_ms=round((time.perf_counter() - started) * 1000, 2),
                config=dataclasses.asdict(cfg),
                alerts=[alert_dict(a) for a in alerts], baseline_alerts=[alert_dict(a) for a in baseline_alerts],
                deda=outcome(alerts, o, onset, offset), baseline=outcome(baseline_alerts, o, onset, offset),
                frames=frames)


def summarize(trials, key):
    critical = [r for r in trials if r[key]["critical"]]
    ambient = [r for r in trials if not r[key]["critical"]]
    n = len(critical)
    lat = [r[key]["latency_ms"] for r in critical if r[key]["latency_ms"] is not None]
    detected = sum(r[key]["detected"] for r in critical)
    ambient_hours = sum(r["duration_ms"] for r in ambient) / 3_600_000
    return dict(events=n, detected=detected,
                wrong_direction_pct=100 * sum(r[key]["wrong_direction"] for r in critical) / n if n else None,
                missed_pct=100 * sum(r[key]["missed"] for r in critical) / n if n else None,
                missed_or_late_pct=100 * sum(r[key]["missed_or_late"] for r in critical) / n if n else None,
                nondirectional_pct=100 * sum(r[key]["nondirectional"] for r in critical) / detected if detected else None,
                latency_p50_ms=float(np.percentile(lat, 50)) if lat else None,
                latency_p95_ms=float(np.percentile(lat, 95)) if lat else None,
                ambient_trials=len(ambient), ambient_hours=ambient_hours,
                false_alerts_per_ambient_hour=sum(r[key]["false_alerts"] for r in ambient) / ambient_hours if ambient_hours else None)


def experiment(raw=None, *, progress=None, cancelled=None):
    """Frozen default policies; acoustic stress tests, not a calibrated benchmark."""
    raw = raw or {}
    seeds = number(raw.get("seeds", 2), "seed count", 1, 5, True)
    full = raw.get("suite", "quick") == "full"
    if raw.get("suite", "quick") not in ("quick", "full"):
        raise ValueError("suite must be quick or full")
    sounds = CLASSES[:4] if full else ("horn", "siren")
    conditions = ("clean", "interference", "clock_fault", "reflection") if full else ("clean", "interference")
    snrs = (20, 0, -10) if full else (20, 0)
    trials = []
    total = seeds * (192 if full else 32) + seeds
    def trial(raw):
        if cancelled and cancelled():
            raise InterruptedError("Experiment cancelled between trials")
        trials.append(simulate(raw, include_frames=False))
        if progress:
            progress(len(trials), total)
    started = time.perf_counter()
    for seed in range(seeds):
        for sound in sounds:
            for condition in conditions:
                for snr in snrs:
                    for angle in (0, 90, 180, 270):
                        # Confidence variation is an assumption, independent of the acoustics.
                        confidence = (.65, .8, .95)[(seed + int(angle / 90)) % 3]
                        trial(dict(sound=sound, condition=condition, snr_db=snr,
                                          angle=angle, confidence=confidence, seed=1000 + seed,
                                          event_ms=384))
        trial(dict(sound="ambient", seed=1000 + seed, event_ms=384))
    return dict(note="New acoustic stress suite using frozen, uncalibrated default DEDA thresholds and baseline tau=0.7. Not a reproduction of the paper's decision-stream benchmark. Class probabilities are scripted; ambient probabilities contain no false confusers, so zero false alerts is not a classifier result. Ambient exposure is very short. No MCU or motor timing.",
                suite="full" if full else "quick", seeds=seeds,
                runtime_ms=round((time.perf_counter() - started) * 1000, 2),
                policies={k: summarize(trials, k) for k in ("baseline", "deda")}, trials=trials)
