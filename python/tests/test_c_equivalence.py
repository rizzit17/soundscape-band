"""Cross-implementation check: the C core (host build) must issue the same
alerts as the Python reference on synthetic streams.
 * double build: must match exactly (same alert times/kinds/classes/motors/k)
 * float build : reported mismatch rate must stay small (float rounding can
   flip decisions that sit exactly on a threshold)."""
import os
import subprocess

import numpy as np
import pytest

from deda.doa import gcc_phat_grid
from deda.policy import DEDA, Config, run
from deda.synth import SynthParams, generate

CDIR = os.path.join(os.path.dirname(__file__), "..", "..", "c")
KIND = {"DIR": 0, "NONDIR": 1, "UPDATE": 2}


def _bin(name):
    p = os.path.join(CDIR, name)
    if not os.path.exists(p):
        pytest.skip("C host build missing - run `make` in c/")
    return p


def _csv(windows, cfg_line):
    lines = [cfg_line]
    for w in windows:
        d = w.dir
        dd = f"1,{float(d.theta_deg)!r},{float(d.closure)!r},{float(d.norm)!r},{float(d.coherence)!r}" if d else "0,0,0,0,0"
        lines.append(f"{float(w.t_ms)!r}," + ",".join(repr(float(p)) for p in w.probs) + "," + dd)
    return "\n".join(lines) + "\n"


def _py(windows, cfg):
    return sorted((round(a.t_ms, 3), KIND[a.kind], a.cls, a.motors, a.k) for a in run(DEDA(cfg), windows))


def _c(binary, windows, cfg):
    line = (f"#CFG {int(cfg.use_dir_reliability)} {int(cfg.sequential)} "
            f"{int(cfg.fallback_nondir)} {int(cfg.wait_for_dir)} {cfg.gamma_spatial}")
    out = subprocess.run([binary], input=_csv(windows, line), capture_output=True, text=True, check=True).stdout
    res = []
    for l in out.strip().splitlines():
        t, k, c, m, kk = l.split(",")
        res.append((round(float(t), 3), int(k), int(c), int(m), int(kk)))
    return sorted(res)


CFGS = [Config(), Config(use_dir_reliability=False), Config(sequential=False),
        Config(fallback_nondir=False), Config(wait_for_dir=False), Config(gamma_spatial=0.75)]


@pytest.mark.parametrize("ci", range(len(CFGS)))
def test_double_build_matches_python_exactly(ci):
    b = _bin("deda_host_double")
    ws, _, _ = generate(SynthParams(duration_s=600), seed=42 + ci)
    assert _py(ws, CFGS[ci]) == _c(b, ws, CFGS[ci])


def test_float_build_close_to_python():
    b = _bin("deda_host_float")
    ws, _, _ = generate(SynthParams(duration_s=1200), seed=7)
    py, c = _py(ws, Config()), _c(b, ws, Config())
    diff = len(set(py) ^ set(c))
    assert diff <= 0.02 * max(len(py), 1), (diff, len(py))


def test_gcc_grid_c_matches_python():
    b = _bin("deda_host_double")
    rng = np.random.default_rng(3)
    fs, n = 16000, 1024
    s = rng.normal(size=n)
    x1 = np.roll(s, 0) + 0.1 * rng.normal(size=n)
    x2 = np.roll(s, 1) + 0.1 * rng.normal(size=n)          # tau_12 = -1 sample
    ref = gcc_phat_grid(x1, x2, fs, 2.0, 0.25)
    # reproduce the PHAT spectrum exactly as the Python reference does
    nfft = 1024
    win = np.hanning(n)
    X1, X2 = np.fft.rfft(x1 * win, nfft), np.fft.rfft(x2 * win, nfft)
    k = np.arange(len(X1))
    f = k * fs / nfft
    sel = (f >= 300) & (f <= 6000)
    G = X1[sel] * np.conj(X2[sel])
    G = G / np.abs(G)
    w = 2 * np.pi * k[sel] / nfft
    lags = np.arange(-2, 2 + 1e-9, 0.25)
    inp = f"{sel.sum()} {lags[0]} 0.25 {len(lags)}\n" + "\n".join(
        f"{float(g.real)!r},{float(g.imag)!r},{float(ww)!r}" for g, ww in zip(G, w)) + "\n"
    out = subprocess.run([b, "gcc"], input=inp, capture_output=True, text=True, check=True).stdout
    tau, coh = map(float, out.strip().split(","))
    assert abs(tau - ref.tau) < 1e-4 and abs(coh - ref.coherence) < 1e-4
    assert abs(tau - (-1.0)) < 0.1
