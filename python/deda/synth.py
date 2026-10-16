"""
Synthetic DECISION-LEVEL stream generator.

!!! It does NOT simulate acoustics. It draws per-window classifier posteriors
and direction observations from parametric distributions whose parameters are
ASSUMPTIONS (listed in SynthParams). Its only purpose is to exercise the
decision logic and the evaluation pipeline. Results on these streams say
nothing about real-world performance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .metrics import Event
from .policy import AMBIENT, CRITICAL, DirObs, Window


@dataclass
class SynthParams:
    hop_ms: float = 64.0
    duration_s: float = 3600.0
    event_rate_per_min: float = 2.0
    ev_dur_s: Tuple[float, float] = (0.6, 3.0)
    ramp_ms: float = 192.0                 # window filling after onset
    strength: Tuple[float, float] = (2.0, 6.0)  # class logit boost (SNR/distance proxy)
    sigma_z: float = 1.0
    p_class_flip: float = 0.08            # per window, another critical class boosted
    amb_bias: float = 2.5
    transient_rate_per_h: float = 120.0    # 1-2 window confusers in ambient
    transient_boost: Tuple[float, float] = (3.0, 6.5)
    persistent_rate_per_h: float = 10.0    # 4-10 window confusers (fool everything)
    persistent_boost: Tuple[float, float] = (2.5, 4.5)
    p_bad_dir: Tuple[float, float, float] = (0.10, 0.25, 0.45)  # 1 m, 3 m, 5 m
    p_flag_bad: float = 0.7                # fraction of bad DOAs the checks catch
    sigma_theta: float = 15.0
    p_missing_dir: float = 0.02
    noise_corr: float = 0.5                # AR(1) correlation of logit noise between windows


def _softmax(z):
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def _good_dir(rng, theta, sp):
    return DirObs((theta + rng.normal(0, sp.sigma_theta)) % 360.0,
                  abs(rng.normal(0, 0.25)), rng.normal(0.95, 0.12),
                  rng.uniform(0.45, 0.9))


def _bad_dir(rng, sp):
    th = rng.uniform(0, 360)
    if rng.random() < sp.p_flag_bad:
        mode = rng.integers(3)
        if mode == 0:
            return DirObs(th, abs(rng.normal(0, 0.25)), rng.normal(0.95, 0.12), rng.uniform(0.05, 0.28))
        if mode == 1:
            return DirObs(th, rng.uniform(0.8, 2.5), rng.normal(0.95, 0.12), rng.uniform(0.3, 0.8))
        return DirObs(th, abs(rng.normal(0, 0.25)), rng.choice([rng.uniform(0.1, 0.5), rng.uniform(1.5, 2.5)]),
                      rng.uniform(0.3, 0.8))
    return DirObs(th, abs(rng.normal(0, 0.25)), rng.normal(0.95, 0.12), rng.uniform(0.3, 0.7))


def generate(sp: SynthParams, seed: int) -> Tuple[List[Window], List[Event], float]:
    rng = np.random.default_rng(seed)
    total_ms = sp.duration_s * 1000.0
    n_win = int(total_ms // sp.hop_ms)
    # ground-truth critical events, non-overlapping
    events: List[Event] = []
    t = rng.exponential(60_000 / sp.event_rate_per_min)
    while t < total_ms - 5000:
        dur = rng.uniform(*sp.ev_dur_s) * 1000
        c = int(rng.choice(CRITICAL))
        theta = float(rng.choice([0, 90, 180, 270]) + rng.normal(0, 5)) % 360
        dist = int(rng.integers(3))
        events.append(Event(t, t + dur, c, theta))
        events[-1].dist = dist             # type: ignore[attr-defined]
        events[-1].strength = rng.uniform(*sp.strength)  # type: ignore[attr-defined]
        t += dur + 2000 + rng.exponential(60_000 / sp.event_rate_per_min)
    # ambient confusers (scheduled in window indices)
    # confusers are real point sources -> they get COHERENT, plausible DOAs
    conf = np.zeros((n_win, 4))
    conf_theta = np.full(n_win, np.nan)
    for rate, (lo, hi), (nlo, nhi) in ((sp.transient_rate_per_h, sp.transient_boost, (1, 2)),
                                       (sp.persistent_rate_per_h, sp.persistent_boost, (4, 10))):
        for _ in range(rng.poisson(rate * sp.duration_s / 3600)):
            i0 = int(rng.integers(n_win - 12))
            n = int(rng.integers(nlo, nhi + 1))
            conf[i0:i0 + n, int(rng.integers(4))] += rng.uniform(lo, hi)
            conf_theta[i0:i0 + n] = rng.uniform(0, 360)
    e_prev = np.zeros(5)
    windows: List[Window] = []
    ei = 0
    for i in range(n_win):
        tm = (i + 1) * sp.hop_ms
        while ei < len(events) and events[ei].offset_ms < tm:
            ei += 1
        ev = events[ei] if ei < len(events) and events[ei].onset_ms <= tm else None
        # AR(1) logit noise: overlapping analysis windows are correlated
        e_prev = sp.noise_corr * e_prev + math.sqrt(1 - sp.noise_corr ** 2) * rng.normal(0, sp.sigma_z, 5)
        z = e_prev.copy()
        if ev is not None:
            f = min(1.0, (tm - ev.onset_ms) / sp.ramp_ms)
            c = ev.cls
            if rng.random() < sp.p_class_flip:
                c = int(rng.choice([k for k in CRITICAL if k != ev.cls]))
            z[c] += ev.strength * f
            z[AMBIENT] += sp.amb_bias * (1 - f)
            if rng.random() < sp.p_missing_dir:
                d = None
            elif rng.random() < sp.p_bad_dir[ev.dist]:
                d = _bad_dir(rng, sp)
            else:
                d = _good_dir(rng, ev.theta, sp)
        else:
            z[AMBIENT] += sp.amb_bias
            z[:4] += conf[i]
            if not np.isnan(conf_theta[i]):
                d = _good_dir(rng, conf_theta[i], sp)
            else:  # diffuse background: weak coherence, arbitrary geometry
                d = DirObs(rng.uniform(0, 360), abs(rng.normal(0, 0.8)), rng.uniform(0.2, 1.8),
                           rng.uniform(0.0, 0.5))
        windows.append(Window(tm, _softmax(z).tolist(), d))
    return windows, events, total_ms
