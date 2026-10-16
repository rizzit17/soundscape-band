"""
SYNTHETIC FREE-FIELD acoustic checks of the direction front-end.
No reverberation, no body/neck shadowing, ideal synchronous mics -> results
are OPTIMISTIC upper bounds and only test the maths/implementation.

Checks
 1. Quadrant accuracy and angular error vs sample rate and SNR (single source).
 2. Closure residual: single source vs two simultaneous sources vs per-mic
    capture offset (shows what closure can and cannot detect).
 3. PHAT coherence of a point source vs a diffuse (isotropic) noise field,
    full band vs high band - tiny arrays see diffuse noise as coherent at
    low frequencies.
"""
import math

import numpy as np

from deda.doa import (estimate_direction, simulate_array, triangle_positions,
                      fractional_delay, C_SOUND, gcc_phat_grid, max_lag_samples, PAIRS)
from deda.policy import quadrant_of

rng = np.random.default_rng(7)
POS = triangle_positions(0.035)


def broadband(n):
    return rng.normal(size=n)


def horn_like(n, fs, f0=420.0):
    t = np.arange(n) / fs
    return sum(np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 6.28)) / h for h in range(1, 12))


def check1():
    print("1) quadrant accuracy / mean |error| (deg), 100 trials per cell, angles 0/90/180/270 +-20 deg")
    for fs in (16000, 48000):
        n = int(0.064 * fs)
        for snr in (20, 10, 0):
            for name, gen in (("broadband", lambda: broadband(n)), ("horn-like", lambda: horn_like(n, fs))):
                for af in (1.0, 0.25):
                    ok, errs = 0, []
                    for _ in range(100):
                        th = (rng.choice([0, 90, 180, 270]) + rng.uniform(-20, 20)) % 360
                        x = simulate_array(gen(), th, POS, fs, snr, rng)
                        d, _ = estimate_direction(x, fs, POS, active_frac=af)
                        ok += quadrant_of(d.theta_deg) == quadrant_of(th)
                        errs.append(abs((d.theta_deg - th + 180) % 360 - 180))
                    print(f"   fs={fs:5d} SNR={snr:3d} dB {name:10s} bins={'all' if af == 1 else 'top25%'}: "
                          f"quadrant {ok:3d}%  mean err {np.mean(errs):5.1f}")


def check2():
    fs, n = 48000, 3072
    print("2) closure |tau01+tau12+tau20| (samples), median over 100 trials, fs=48 kHz, SNR 20 dB")
    cases = {
        "single source": dict(),
        "two sources, equal level": dict(interferer=True),
        "mic 2 offset by +3 samples": dict(mic_offsets=(0, 0, 3.0)),
    }
    for name, kw in cases.items():
        cl, nm = [], []
        for _ in range(100):
            th = rng.uniform(0, 360)
            inter = (broadband(n), (th + rng.uniform(90, 270)) % 360, 1.0) if kw.get("interferer") else None
            x = simulate_array(broadband(n), th, POS, fs, 20, rng, kw.get("mic_offsets", (0, 0, 0)), inter)
            d, _ = estimate_direction(x, fs, POS)
            cl.append(d.closure)
            nm.append(d.norm)
        print(f"   {name:28s}: closure {np.median(cl):.2f}   |v| {np.median(nm):.2f} (1.0 expected)")


def diffuse(n, fs, n_src=64):
    out = np.zeros((3, n))
    for _ in range(n_src):
        th = rng.uniform(0, 360)
        u = np.array([math.sin(math.radians(th)), math.cos(math.radians(th))])
        s = broadband(n)
        for m in range(3):
            out[m] += fractional_delay(s, -(POS[m] @ u) / C_SOUND * fs)
    return out


def check3():
    fs, n = 48000, 3072
    L = max_lag_samples(POS, fs)
    print("3) min-pair PHAT coherence, median of 50 trials (fs=48 kHz, no extra noise)")
    for band in ((300, 6000), (2500, 8000)):
        pt = [min(gcc_phat_grid(x[i], x[j], fs, L, band=band).coherence for i, j in PAIRS)
              for x in (simulate_array(broadband(n), rng.uniform(0, 360), POS, fs, 20, rng) for _ in range(50))]
        df = [min(gcc_phat_grid(x[i], x[j], fs, L, band=band).coherence for i, j in PAIRS)
              for x in (diffuse(n, fs) for _ in range(50))]
        print(f"   band {band[0]:>4}-{band[1]} Hz: point source {np.median(pt):.2f}   diffuse field {np.median(df):.2f}")


if __name__ == "__main__":
    print("SYNTHETIC free-field checks - optimistic, not a substitute for recorded data\n")
    check1()
    check2()
    check3()
