"""Unit tests for the DEDA decision logic and the direction front-end.
All inputs are synthetic. Passing these tests shows the logic does what the
specification says; it does NOT show real-world benefit."""
import math
import random

import numpy as np
import pytest

from deda.doa import (direction_from_tdoa, estimate_direction, ls_matrix,
                      simulate_array, triangle_positions, C_SOUND, PAIRS)
from deda.policy import (DEDA, MOTORS_ALL, MOTOR_BACK, MOTOR_FRONT, MOTOR_LEFT,
                         MOTOR_RIGHT, Config, DirObs, FixedThreshold, Window,
                         circ_dist, motors_for_angle, run)

H = 64.0


def probs(c=None, p=0.0):
    """Posterior with mass p on class c, rest on ambient."""
    v = [0.01, 0.01, 0.01, 0.01, 0.0]
    if c is not None:
        v[c] = p
    v[4] = max(0.0, 1.0 - sum(v))
    return v


GOOD = lambda th: DirObs(th, 0.05, 1.0, 0.8)
BAD = DirObs(123.0, 2.0, 1.0, 0.8)          # fails closure
DIFFUSE = DirObs(200.0, 0.1, 1.0, 0.1)      # fails coherence


def stream(seq):
    return [Window((i + 1) * H, p, d) for i, (p, d) in enumerate(seq)]


# ---------------------------------------------------------------- geometry
def test_closure_zero_and_angle_recovery_exact_tdoas():
    pos, fs = triangle_positions(0.035), 48000
    P = ls_matrix(pos, fs)
    for th in (0, 45, 90, 180, 270, 359):
        u = np.array([math.sin(math.radians(th)), math.cos(math.radians(th))])
        t = [-(pos[m] @ u) / C_SOUND * fs for m in range(3)]
        taus = [t[i] - t[j] for i, j in PAIRS]
        d = direction_from_tdoa(taus, [1, 1, 1], P)
        assert d.closure < 1e-9
        assert abs(d.norm - 1) < 1e-9
        assert circ_dist(d.theta_deg, th) < 1e-6


def test_closure_invariant_to_per_mic_offset_but_norm_is_not():
    """Documented limitation: unsynchronised capture is invisible to closure."""
    pos, fs = triangle_positions(0.035), 48000
    P = ls_matrix(pos, fs)
    u = np.array([0.0, 1.0])
    t = [-(pos[m] @ u) / C_SOUND * fs for m in range(3)]
    t[2] += 2.0
    d = direction_from_tdoa([t[i] - t[j] for i, j in PAIRS], [1, 1, 1], P)
    assert d.closure < 1e-9
    assert abs(d.norm - 1) > 0.1


@pytest.mark.parametrize("th", [0, 90, 180, 270])
def test_gcc_quadrant_free_field(th):
    rng = np.random.default_rng(th)
    pos, fs = triangle_positions(0.035), 16000
    x = simulate_array(rng.normal(size=1024), th, pos, fs, 15, rng)
    d, _ = estimate_direction(x, fs, pos)
    assert circ_dist(d.theta_deg, th) < 20


# ------------------------------------------------------------- circular maths
def test_wraparound_mean_is_front_not_back():
    ded = DEDA()
    for th in (350.0, 10.0):
        ded._add_dir(GOOD(th))
    ok, theta, m = ded._dir_decision()
    assert ok and circ_dist(theta, 0.0) < 1e-6 and m == MOTOR_FRONT


def test_boundary_drives_two_adjacent_motors():
    assert motors_for_angle(45.0, 10.0) == MOTOR_FRONT | MOTOR_RIGHT
    assert motors_for_angle(314.0, 10.0) == MOTOR_FRONT | MOTOR_LEFT
    assert motors_for_angle(100.0, 10.0) == MOTOR_RIGHT


def test_opposite_directions_are_not_confident():
    ded = DEDA()
    ded._add_dir(GOOD(0.0))
    ded._add_dir(GOOD(180.0))
    ok, _, m = ded._dir_decision()
    assert not ok and m == MOTORS_ALL


# ------------------------------------------------------------- decision rules
def test_high_confidence_immediate_directional_alert():
    a = run(DEDA(), stream([(probs(0, 0.97), GOOD(90))]))
    assert len(a) == 1 and a[0].kind == "DIR" and a[0].k == 0 and a[0].motors == MOTOR_RIGHT


def test_intermediate_confidence_is_deferred_not_dropped():
    seq = [(probs(1, 0.80), GOOD(180))] * 3
    a = run(DEDA(), stream(seq))
    assert len(a) == 1 and a[0].k >= 1 and a[0].motors == MOTOR_BACK


def test_isolated_moderate_transient_is_rejected():
    seq = [(probs(2, 0.85), DIFFUSE)] + [(probs(), DIFFUSE)] * 5
    assert run(DEDA(), stream(seq)) == []


def test_class_confident_direction_unreliable_gives_nondirectional_alert():
    seq = [(probs(0, 0.95), BAD)] * 4
    a = run(DEDA(), stream(seq))
    assert len(a) == 1 and a[0].kind == "NONDIR" and a[0].motors == MOTORS_ALL
    assert a[0].k <= Config().K


def test_missing_doa_is_handled():
    seq = [(probs(3, 0.95), None)] * 4
    a = run(DEDA(), stream(seq))
    assert len(a) == 1 and a[0].kind == "NONDIR"


def test_ongoing_event_alerts_once():
    seq = [(probs(0, 0.95), GOOD(0))] * 30
    a = [x for x in run(DEDA(), stream(seq)) if x.kind != "UPDATE"]
    assert len(a) == 1


def test_event_can_realert_after_it_ends():
    seq = [(probs(0, 0.95), GOOD(0))] * 5 + [(probs(), None)] * 5 + [(probs(0, 0.95), GOOD(0))] * 3
    a = run(DEDA(), stream(seq))
    assert len(a) == 2


def test_moving_source_triggers_update():
    seq = [(probs(1, 0.95), GOOD(0))] * 5 + [(probs(1, 0.95), GOOD(90))] * 40
    a = run(DEDA(), stream(seq))
    ups = [x for x in a if x.kind == "UPDATE"]
    assert a[0].kind == "DIR" and a[0].motors == MOTOR_FRONT
    assert ups and ups[0].motors == MOTOR_RIGHT


def test_nondirectional_alert_is_refined_when_direction_appears():
    seq = [(probs(0, 0.95), BAD)] * 4 + [(probs(0, 0.95), GOOD(270))] * 30
    a = run(DEDA(), stream(seq))
    assert a[0].kind == "NONDIR"
    assert any(x.kind == "UPDATE" and x.motors == MOTOR_LEFT for x in a)


def test_second_hazard_class_during_refractory_still_alerts():
    seq = [(probs(0, 0.95), GOOD(0))] * 3
    p = probs(0, 0.5); p[1] = 0.45; p[4] = 0.03
    seq += [(p, GOOD(0))]                      # transition window
    p2 = probs(1, 0.9); p2[0] = 0.05; p2[4] = 0.03
    seq += [(p2, GOOD(180))] * 3
    a = [x for x in run(DEDA(), stream(seq)) if x.kind != "UPDATE"]
    assert [x.cls for x in a] == [0, 1]


def test_strgf_gate_ablation_drops_alert_when_direction_bad():
    cfg = Config(fallback_nondir=False)
    seq = [(probs(0, 0.95), BAD)] * 3
    assert run(DEDA(cfg), stream(seq)) == []


def test_baseline_b_uses_raw_direction():
    a = run(FixedThreshold(0.7, True), stream([(probs(0, 0.9), BAD)]))
    assert a[0].kind == "DIR" and a[0].theta == BAD.theta_deg


# ----------------------------------------------------- property: deadline
def test_deadline_never_exceeded_random_streams():
    """Within an evidence episode, no first alert is issued after index K."""
    rnd = random.Random(0)
    cfg = Config()
    for _ in range(300):
        seq = []
        for _ in range(40):
            c = rnd.randrange(4)
            p = probs(c, rnd.random())
            r = rnd.random()
            d = None if r < 0.2 else (BAD if r < 0.5 else GOOD(rnd.uniform(0, 360)))
            seq.append((p, d))
        for a in run(DEDA(cfg), stream(seq)):
            if a.kind != "UPDATE":
                assert 0 <= a.k <= cfg.K


def test_state_is_bounded():
    ded = DEDA()
    rnd = random.Random(1)
    for i in range(5000):
        ded.step(Window(i * H, probs(rnd.randrange(4), rnd.random()), GOOD(rnd.uniform(0, 360))))
    assert len(ded.sup.tracks) <= 4
