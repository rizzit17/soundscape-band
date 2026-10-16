"""
DEDA - Dual-Evidence Deadline Alerting  (provisional name)
=========================================================

A decision policy that sits AFTER the existing SoundScape Band branches:
    Path A (GCC-PHAT TDOA)  -> per-window direction observation
    Path B (MFCC + 1D-CNN)  -> per-window calibrated class posteriors
and decides, per window, whether to: alert with direction, alert without
direction, wait for one more window, or reject.

Core ideas (see report, Section 5):
 1. "What" and "where" are decided by SEPARATE evidence statistics.
 2. Class evidence uses a deadline-truncated sequential test: an immediate
    path for high-confidence windows, otherwise evidence is accumulated with
    a threshold that relaxes linearly to a floor at the deadline index K.
 3. Direction evidence is accepted per window only if it passes geometric
    consistency checks (TDOA closure, plane-wave norm, PHAT coherence) and is
    aggregated with circular (unit-vector) statistics.
 4. Direction uncertainty degrades the SPATIAL SPECIFICITY of the alert
    (non-directional pattern) instead of suppressing it -> it cannot cause a
    missed hazard by itself.
 5. Per-class suppression prevents repeated alerts for an ongoing event;
    direction updates are issued only on a confident large direction change.

STATUS: reference implementation for offline simulation. Validated on
SYNTHETIC decision streams only. Thresholds below are PLACEHOLDERS that must
be selected on a calibration split of real recordings (report, Table P).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

CLASSES = ("horn", "siren", "shout", "beep", "ambient")
CRITICAL = (0, 1, 2, 3)
AMBIENT = 4

MOTOR_FRONT, MOTOR_RIGHT, MOTOR_BACK, MOTOR_LEFT = 1, 2, 4, 8
MOTORS_ALL = 15
_QUAD_MASK = (MOTOR_FRONT, MOTOR_RIGHT, MOTOR_BACK, MOTOR_LEFT)  # 0,90,180,270


# ---------------------------------------------------------------- helpers
def logit(p: float, clip: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return max(-clip, min(clip, math.log(p / (1 - p))))


def wrap180(a: float) -> float:
    """Wrap an angle difference to (-180, 180]."""
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


def circ_dist(a: float, b: float) -> float:
    return abs(wrap180(a - b))


def motors_for_angle(theta: float, beta_min: float) -> int:
    """Nearest quadrant motor; two adjacent motors if within beta_min of a
    quadrant boundary (boundary = 45, 135, 225, 315 deg)."""
    q = int(math.floor((theta % 360.0) / 90.0 + 0.5)) % 4   # half-up, same as C
    off = wrap180(theta - 90.0 * q)            # (-45, 45]
    margin = 45.0 - abs(off)
    if margin >= beta_min:
        return _QUAD_MASK[q]
    nb = (q + (1 if off > 0 else -1)) % 4
    return _QUAD_MASK[q] | _QUAD_MASK[nb]


def quadrant_of(theta: float) -> int:
    return int(math.floor((theta % 360.0) / 90.0 + 0.5)) % 4


# ------------------------------------------------------------ data types
@dataclass
class DirObs:
    theta_deg: float
    closure: float      # samples
    norm: float         # |v|
    coherence: float    # [0,1]


@dataclass
class Window:
    t_ms: float                        # end time of the analysis window
    probs: Sequence[float]             # calibrated posteriors, len 5
    dir: Optional[DirObs] = None       # None = DOA missing/invalid frame


@dataclass
class Alert:
    t_ms: float
    kind: str           # "DIR", "NONDIR", "UPDATE"
    cls: int
    motors: int         # bitmask F=1,R=2,B=4,L=8
    theta: Optional[float]
    k: int              # window index inside the evidence episode (0 = immediate)


@dataclass
class Config:
    # timing
    hop_ms: float = 64.0
    deadline_ms: float = 300.0
    proc_ms: float = 60.0              # MEASURE on target MCU; placeholder
    # class evidence
    p_open: float = 0.35               # open an evidence episode
    clip: float = 4.0                  # logit clip (bounded influence of one window)
    kappa: float = 0.6                 # discount for later, overlapping windows
    h_hi: Sequence[float] = (2.0, 2.2, 2.4, 2.0)   # immediate thresholds per critical class
    h_lo: Sequence[float] = (1.6, 1.8, 2.0, 1.6)   # floor at deadline per class
    h_urgent: Sequence[float] = (3.0, 3.0, 3.2, 3.0)  # >= this: never wait for direction
    margin: float = 0.5                # lead over the runner-up critical class
    h_reject: float = -1.0             # all critical evidence below -> early reject
    # direction reliability
    rho_min: float = 0.30              # min PHAT coherence (all pairs)
    rho_strong: float = 0.50           # single-window direction needs this
    closure_max: float = 0.75          # samples (depends on fs, array) - calibrate
    norm_lo: float = 0.6
    norm_hi: float = 1.4
    r_min: float = 0.75                # circular concentration over valid windows
    beta_min: float = 10.0             # deg; boundary band -> two motors
    # suppression / updates
    p_off: float = 0.20
    m_off: int = 3                     # consecutive windows below p_off -> event over
    t_max_ms: float = 8000.0           # re-alert reminder for a persistent hazard
    move_deg: float = 60.0             # confident change -> UPDATE alert
    upd_gap_ms: float = 1000.0
    upd_alpha: float = 0.5             # EMA weight of tracked direction
    # optional coupling (hypothesis H3, default OFF): raise the class threshold
    # by gamma_spatial while no confident direction exists (diffuse-noise prior)
    gamma_spatial: float = 0.0
    # ablation switches
    use_dir_reliability: bool = True
    sequential: bool = True
    fallback_nondir: bool = True
    wait_for_dir: bool = True

    @property
    def K(self) -> int:
        """Deadline index: latest window index k with (k+1)*hop + proc <= D."""
        if not self.sequential:
            return 0
        return max(0, int((self.deadline_ms - self.proc_ms) // self.hop_ms) - 1)


def dir_valid(d: Optional[DirObs], cfg: Config) -> bool:
    if d is None:
        return False
    if not cfg.use_dir_reliability:
        return True
    return (d.coherence >= cfg.rho_min and d.closure <= cfg.closure_max
            and cfg.norm_lo <= d.norm <= cfg.norm_hi)


# ------------------------------------------------------- suppression state
@dataclass
class _Track:
    t_alert: float
    last_motors: int
    last_theta: Optional[float]
    below: int = 0
    ex: float = 0.0     # EMA of unit vector (x = sin, y = cos)
    ey: float = 0.0
    ew: float = 0.0
    t_upd: float = -1e9


class _Suppressor:
    """Per-class refractory + direction-update logic (shared by all policies
    so that baselines are not penalised for repeated alerts)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.tracks: dict[int, _Track] = {}

    def active(self, c: int) -> bool:
        return c in self.tracks

    def start(self, c: int, t: float, motors: int, theta: Optional[float]):
        tr = _Track(t_alert=t, last_motors=motors, last_theta=theta, t_upd=t)
        if theta is not None:
            tr.ex, tr.ey, tr.ew = math.sin(math.radians(theta)), math.cos(math.radians(theta)), 1.0
        self.tracks[c] = tr

    def step(self, w: Window, updates_enabled: bool = True) -> List[Alert]:
        cfg, out = self.cfg, []
        for c in list(self.tracks):
            tr = self.tracks[c]
            p = w.probs[c]
            tr.below = tr.below + 1 if p < cfg.p_off else 0
            if tr.below >= cfg.m_off or w.t_ms - tr.t_alert >= cfg.t_max_ms:
                del self.tracks[c]
                continue
            if not updates_enabled or p < cfg.p_open or not dir_valid(w.dir, cfg):
                continue
            th = math.radians(w.dir.theta_deg)
            a = cfg.upd_alpha
            tr.ex = (1 - a) * tr.ex + a * math.sin(th)
            tr.ey = (1 - a) * tr.ey + a * math.cos(th)
            tr.ew = (1 - a) * tr.ew + a
            r = math.hypot(tr.ex, tr.ey) / max(tr.ew, 1e-9)
            if r < cfg.r_min or w.t_ms - tr.t_upd < cfg.upd_gap_ms:
                continue
            theta = math.degrees(math.atan2(tr.ex, tr.ey)) % 360.0
            if tr.last_theta is None or circ_dist(theta, tr.last_theta) >= cfg.move_deg:
                m = motors_for_angle(theta, cfg.beta_min)
                out.append(Alert(w.t_ms, "UPDATE", c, m, theta, -1))
                tr.last_theta, tr.last_motors, tr.t_upd = theta, m, w.t_ms
        return out


# ------------------------------------------------------------------ DEDA
class DEDA:
    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or Config()
        self.sup = _Suppressor(self.cfg)
        self._reset_episode()

    def _reset_episode(self):
        self.open = False
        self.k = 0
        self.L = [0.0] * 4          # class evidence per critical class
        self.Rx = self.Ry = self.W = 0.0
        self.n_dir = 0
        self.max_coh = 0.0
        self.latched: Optional[int] = None

    # -- direction aggregate -------------------------------------------
    def _add_dir(self, d: Optional[DirObs]):
        if not dir_valid(d, self.cfg):
            return
        w = d.coherence if self.cfg.use_dir_reliability else 1.0
        th = math.radians(d.theta_deg)
        self.Rx += w * math.sin(th)
        self.Ry += w * math.cos(th)
        self.W += w
        self.n_dir += 1
        self.max_coh = max(self.max_coh, d.coherence)

    def _dir_decision(self):
        """Return (confident, theta, motors)."""
        cfg = self.cfg
        if self.n_dir == 0:
            return False, None, MOTORS_ALL
        if self.n_dir == 1 and cfg.use_dir_reliability and self.max_coh < cfg.rho_strong:
            return False, None, MOTORS_ALL
        r = math.hypot(self.Rx, self.Ry) / max(self.W, 1e-9)
        if r < cfg.r_min:
            return False, None, MOTORS_ALL
        theta = math.degrees(math.atan2(self.Rx, self.Ry)) % 360.0
        return True, theta, motors_for_angle(theta, cfg.beta_min)

    def _emit(self, w: Window, c: int, dir_ok: bool, theta, motors) -> Alert:
        kind = "DIR" if dir_ok else "NONDIR"
        a = Alert(w.t_ms, kind, c, motors if dir_ok else MOTORS_ALL,
                  theta if dir_ok else None, self.k)
        self.sup.start(c, w.t_ms, a.motors, a.theta)
        self._reset_episode()
        return a

    # -- main step --------------------------------------------------------
    def step(self, w: Window) -> List[Alert]:
        cfg = self.cfg
        out = self.sup.step(w)
        cand = [c for c in CRITICAL if not self.sup.active(c)]

        if not self.open:
            if not cand or max(w.probs[c] for c in cand) < cfg.p_open:
                return out
            self.open, self.k = True, 0
        else:
            self.k += 1
        K = cfg.K

        # evidence update -------------------------------------------------
        gain = 1.0 if self.k == 0 else cfg.kappa
        for c in CRITICAL:
            if c in cand:
                self.L[c] += gain * logit(w.probs[c], cfg.clip)
            else:
                self.L[c] = -1e9  # suppressed class cannot win
        self._add_dir(w.dir)

        # class already decided, waiting for direction only ---------------
        if self.latched is not None:
            ok, th, m = self._dir_decision()
            if ok or self.k >= K:
                if ok or cfg.fallback_nondir:
                    out.append(self._emit(w, self.latched, ok, th, m))
                else:
                    self._reset_episode()          # STRGF-style gate: drop
            return out

        # class decision -----------------------------------------------------
        if not cand:
            self._reset_episode()
            return out
        cstar = max(cand, key=lambda c: self.L[c])
        runner = max([self.L[c] for c in cand if c != cstar], default=-1e9)
        frac = self.k / K if K > 0 else 1.0
        h = cfg.h_hi[cstar] - (cfg.h_hi[cstar] - cfg.h_lo[cstar]) * frac
        ok, th, m = self._dir_decision()
        if not ok and cfg.gamma_spatial > 0.0 and self.k < K:
            h += cfg.gamma_spatial       # never applied at the deadline index
        accepted = self.L[cstar] >= h and (self.L[cstar] - runner) >= cfg.margin

        if accepted:
            if ok:
                out.append(self._emit(w, cstar, True, th, m))
            elif (cfg.wait_for_dir and self.k < K
                  and self.L[cstar] < cfg.h_urgent[cstar]):
                self.latched = cstar               # wait <= K - k windows
            elif cfg.fallback_nondir:
                out.append(self._emit(w, cstar, False, None, MOTORS_ALL))
            else:
                self._reset_episode()
            return out

        if max(self.L[c] for c in cand) <= cfg.h_reject or self.k >= K:
            self._reset_episode()                  # reject / timeout
        return out


# -------------------------------------------------------------- baselines
class FixedThreshold:
    """Baseline A (use_direction=False): classifier-only, all motors.
    Baseline B (use_direction=True): fixed threshold + raw single-window DOA
    mapped to the nearest motor (no reliability check, no temporal logic).
    Both use the same per-class suppression as DEDA, for a fair comparison.
    """

    def __init__(self, tau: float = 0.7, use_direction: bool = True,
                 cfg: Optional[Config] = None):
        self.tau = tau
        self.use_direction = use_direction
        self.cfg = cfg or Config(use_dir_reliability=False)
        self.sup = _Suppressor(self.cfg)

    def step(self, w: Window) -> List[Alert]:
        out = self.sup.step(w, updates_enabled=False)
        cand = [c for c in CRITICAL if not self.sup.active(c)]
        if not cand:
            return out
        c = max(cand, key=lambda i: w.probs[i])
        if w.probs[c] < self.tau:
            return out
        if self.use_direction and w.dir is not None:
            q = quadrant_of(w.dir.theta_deg)
            a = Alert(w.t_ms, "DIR", c, _QUAD_MASK[q], w.dir.theta_deg, 0)
        else:
            a = Alert(w.t_ms, "NONDIR", c, MOTORS_ALL, None, 0)
        self.sup.start(c, w.t_ms, a.motors, a.theta)
        out.append(a)
        return out


def run(policy, windows: Sequence[Window]) -> List[Alert]:
    alerts: List[Alert] = []
    for w in windows:
        alerts.extend(policy.step(w))
    return alerts
