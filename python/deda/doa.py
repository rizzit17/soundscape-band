"""
Direction front-end for a 3-microphone planar array (SoundScape Band).

STATUS: reference code, verified only on SYNTHETIC signals (see tests/).
It has NOT been validated on recorded audio or on the RP2040/ESP32.

Conventions
-----------
* Body frame: x = wearer's right, y = wearer's front.
* Azimuth theta is measured CLOCKWISE from the front, in degrees:
  0 = front, 90 = right, 180 = back, 270 = left (matches the test layout).
* tau_ij = t_i - t_j  (arrival time at mic i minus arrival time at mic j),
  in SAMPLES. Pairs are ordered (0,1), (1,2), (2,0) so that the closure
  tau_01 + tau_12 + tau_20 is identically zero for error-free TDOAs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

C_SOUND = 343.0  # m/s at ~20 degC
PAIRS = ((0, 1), (1, 2), (2, 0))


def triangle_positions(side_m: float = 0.035) -> np.ndarray:
    """Equilateral triangle, centroid at origin, mic 0 pointing to the front.

    Returns (3, 2) array of (x, y) in metres. Replace with the measured
    geometry of the actual band; a neckband is NOT a free-field array.
    """
    r = side_m / math.sqrt(3.0)  # circumradius
    angles = np.deg2rad([0.0, 120.0, 240.0])  # clockwise from front
    return np.stack([r * np.sin(angles), r * np.cos(angles)], axis=1)


def max_lag_samples(pos: np.ndarray, fs: float) -> float:
    d = max(np.linalg.norm(pos[i] - pos[j]) for i, j in PAIRS)
    return d / C_SOUND * fs


# ---------------------------------------------------------------- GCC-PHAT
@dataclass
class GccResult:
    tau: float          # samples, fractional
    coherence: float    # PHAT-normalised peak height in [0, 1]


def gcc_phat_grid(xi: np.ndarray, xj: np.ndarray, fs: float, max_lag: float,
                  step: float = 0.25, band=(300.0, 6000.0),
                  active_frac: float = 1.0) -> GccResult:
    """GCC-PHAT evaluated directly on a fractional lag grid.

    Because a 3-4 cm array has |tau| < ~2 samples at 16 kHz (< ~5 at 48 kHz),
    only a handful of lags are physically possible. Evaluating the PHAT
    cross-spectrum at those lags (direct DFT on a 0.25-sample grid) is cheaper
    than a full IFFT and avoids integer-lag quantisation.

    coherence = Re{ sum_k G_k e^{j w_k tau} } / K  with |G_k| = 1, so it equals
    1 for a perfectly coherent single delay and ~0 for incoherent noise.
    """
    n = len(xi)
    nfft = 1 << (n - 1).bit_length()
    win = np.hanning(n)
    Xi = np.fft.rfft(xi * win, nfft)
    Xj = np.fft.rfft(xj * win, nfft)
    k = np.arange(len(Xi))
    f = k * fs / nfft
    sel = (f >= band[0]) & (f <= band[1])
    if active_frac < 1.0:
        # keep only the strongest cross-power bins: harmonic sources (horns,
        # sirens, beeps) leave most bins noise-only, which PHAT would
        # otherwise weight equally with the signal bins.
        cp = np.abs(Xi * np.conj(Xj))
        idx = np.flatnonzero(sel)
        keep = max(8, int(len(idx) * active_frac))
        thr = np.sort(cp[idx])[-keep]
        sel = sel & (cp >= thr)
    cross = Xi[sel] * np.conj(Xj[sel])
    mag = np.abs(cross)
    good = mag > 1e-12
    G = np.zeros_like(cross)
    G[good] = cross[good] / mag[good]
    w = 2.0 * np.pi * k[sel] / nfft  # rad/sample
    lags = np.arange(-math.ceil(max_lag), math.ceil(max_lag) + 1e-9, step)
    # R(l) = Re sum_k G_k e^{+j w_k l}; peak at l = t_i - t_j
    R = np.real(np.exp(1j * np.outer(lags, w)) @ G) / max(int(sel.sum()), 1)
    i = int(np.argmax(R))
    tau = float(lags[i])
    # parabolic refinement on the fine grid
    if 0 < i < len(R) - 1:
        a, b, c = R[i - 1], R[i], R[i + 1]
        den = a - 2 * b + c
        if abs(den) > 1e-12:
            tau += 0.5 * (a - c) / den * step
    return GccResult(tau=tau, coherence=float(max(R[i], 0.0)))


# ------------------------------------------------- geometry + reliability
@dataclass
class DirectionObs:
    theta_deg: float    # azimuth, clockwise from front, [0, 360)
    closure: float      # |tau_01 + tau_12 + tau_20|, samples
    norm: float         # |v| of LS plane-wave solution (1 = in-plane far field)
    coherence: float    # min over pairs of PHAT peak height, [0, 1]


def ls_matrix(pos: np.ndarray, fs: float) -> np.ndarray:
    """Pseudo-inverse P (2x3) mapping TDOA vector -> direction vector v.

    Plane wave from unit direction u (pointing to the source):
        t_i = -(m_i . u)/c   =>   tau_ij = -(m_i - m_j) . u * fs / c
    """
    A = np.array([-(pos[i] - pos[j]) * fs / C_SOUND for i, j in PAIRS])  # 3x2
    return np.linalg.pinv(A)


def direction_from_tdoa(taus, cohs, P: np.ndarray) -> DirectionObs:
    taus = np.asarray(taus, dtype=float)
    v = P @ taus  # (vx, vy)
    theta = math.degrees(math.atan2(v[0], v[1])) % 360.0
    return DirectionObs(theta_deg=theta,
                        closure=float(abs(taus.sum())),
                        norm=float(np.hypot(v[0], v[1])),
                        coherence=float(min(cohs)))


def estimate_direction(frames: np.ndarray, fs: float, pos: np.ndarray,
                       step: float = 0.25, band=(300.0, 6000.0),
                       active_frac: float = 1.0) -> tuple[DirectionObs, np.ndarray]:
    """frames: (3, N) synchronous samples. Returns (DirectionObs, taus)."""
    L = max_lag_samples(pos, fs)
    res = [gcc_phat_grid(frames[i], frames[j], fs, L, step, band, active_frac) for i, j in PAIRS]
    taus = np.array([r.tau for r in res])
    obs = direction_from_tdoa(taus, [r.coherence for r in res], ls_matrix(pos, fs))
    return obs, taus


# ------------------------------------------------------ synthetic signals
def fractional_delay(x: np.ndarray, d: float) -> np.ndarray:
    """Delay x by d samples (circular, frequency domain). Synthetic use only."""
    n = len(x)
    X = np.fft.rfft(x)
    w = 2 * np.pi * np.arange(len(X)) / n
    return np.fft.irfft(X * np.exp(-1j * w * d), n)


def simulate_array(src: np.ndarray, theta_deg: float, pos: np.ndarray, fs: float,
                   snr_db: float = 20.0, rng=None, mic_offsets=(0.0, 0.0, 0.0),
                   interferer=None) -> np.ndarray:
    """Far-field free-field plane wave + independent white noise per mic.

    interferer: optional (signal, theta_deg, gain) second plane wave.
    mic_offsets: per-mic sample offsets (models unsynchronised I2S capture).
    NOTE: no reverberation, no body shadowing -> optimistic.
    """
    rng = np.random.default_rng() if rng is None else rng
    th = math.radians(theta_deg)
    u = np.array([math.sin(th), math.cos(th)])
    out = []
    for m in range(3):
        t = -(pos[m] @ u) / C_SOUND * fs + mic_offsets[m]
        x = fractional_delay(src, t)
        if interferer is not None:
            s2, th2, g = interferer
            u2 = np.array([math.sin(math.radians(th2)), math.cos(math.radians(th2))])
            x = x + g * fractional_delay(s2, -(pos[m] @ u2) / C_SOUND * fs)
        p = np.mean(x ** 2)
        x = x + rng.normal(0, math.sqrt(p / 10 ** (snr_db / 10)), len(x))
        out.append(x)
    return np.stack(out)
