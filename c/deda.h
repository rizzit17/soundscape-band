/*
 * DEDA - Dual-Evidence Deadline Alerting (provisional name)
 * Embedded-oriented reference implementation for SoundScape Band.
 *
 * STATUS: compiled and tested on a HOST PC only, against the Python
 * reference on synthetic streams (tests/test_c_equivalence.py).
 * NOT yet compiled for or measured on RP2040 / ESP32.
 *
 * Design rules: no dynamic allocation, fixed-size state, O(1) work per
 * window (independent of stream length), no recursion.
 * Arithmetic: DEDA_REAL defaults to float (ESP32 has an FPU; the RP2040 uses
 * its optimised ROM soft-float). The decision core runs once per hop
 * (~15 times/s) with a few hundred operations, so float is not a bottleneck;
 * integer-only arithmetic is used where it matters (audio, see doa_gcc.c).
 */
#ifndef DEDA_H
#define DEDA_H

#include <stdint.h>

#ifndef DEDA_REAL
#define DEDA_REAL float
#endif
typedef DEDA_REAL dreal;

#define DEDA_NCLS 5          /* horn, siren, shout, beep, ambient */
#define DEDA_NCRIT 4         /* classes 0..3 are safety-critical   */
#define DEDA_AMBIENT 4

#define DEDA_MOTOR_FRONT 1u
#define DEDA_MOTOR_RIGHT 2u
#define DEDA_MOTOR_BACK 4u
#define DEDA_MOTOR_LEFT 8u
#define DEDA_MOTORS_ALL 15u

typedef enum { DEDA_ALERT_DIR = 0, DEDA_ALERT_NONDIR = 1, DEDA_ALERT_UPDATE = 2 } deda_kind_t;

typedef struct {
    /* timing */
    dreal hop_ms, deadline_ms, proc_ms;
    /* class evidence */
    dreal p_open, clip, kappa;
    dreal h_hi[DEDA_NCRIT], h_lo[DEDA_NCRIT], h_urgent[DEDA_NCRIT];
    dreal margin, h_reject;
    /* direction reliability */
    dreal rho_min, rho_strong, closure_max, norm_lo, norm_hi, r_min, beta_min;
    /* suppression / updates */
    dreal p_off; uint8_t m_off; dreal t_max_ms, move_deg, upd_gap_ms, upd_alpha;
    dreal gamma_spatial;
    /* ablation switches */
    uint8_t use_dir_reliability, sequential, fallback_nondir, wait_for_dir;
} deda_config_t;

typedef struct {
    dreal theta_deg, closure, norm, coherence;
} deda_dir_t;

typedef struct {
    dreal t_ms;
    dreal probs[DEDA_NCLS];  /* calibrated posteriors */
    uint8_t has_dir;         /* 0 -> DOA missing for this window */
    deda_dir_t dir;
} deda_window_t;

typedef struct {
    dreal t_ms;
    uint8_t kind;            /* deda_kind_t */
    uint8_t cls;
    uint8_t motors;          /* bitmask F=1 R=2 B=4 L=8 */
    uint8_t has_theta;
    dreal theta;
    int8_t k;                /* episode index; -1 for UPDATE */
} deda_alert_t;

typedef struct {
    uint8_t active, last_motors, has_theta, below;
    dreal t_alert, last_theta, ex, ey, ew, t_upd;
    uint32_t order;          /* insertion order (mirrors reference) */
} deda_track_t;

typedef struct {
    deda_config_t cfg;
    uint8_t K;
    /* episode */
    uint8_t open, k, n_dir;
    int8_t latched;          /* -1 none */
    dreal L[DEDA_NCRIT];
    dreal Rx, Ry, W, max_coh;
    /* suppression */
    deda_track_t tr[DEDA_NCRIT];
    uint32_t next_order;
} deda_state_t;

#define DEDA_MAX_ALERTS_PER_STEP (DEDA_NCRIT + 1)

void deda_default_config(deda_config_t *c);
void deda_init(deda_state_t *s, const deda_config_t *c);
/* Process one analysis window; writes up to DEDA_MAX_ALERTS_PER_STEP alerts,
 * returns the number written. Worst-case cost is constant. */
int deda_step(deda_state_t *s, const deda_window_t *w, deda_alert_t *out);

/* helpers (exposed for tests) */
uint8_t deda_motors_for_angle(dreal theta, dreal beta_min);
dreal deda_wrap180(dreal a);

/* Direction front-end helpers (doa_gcc.c) ---------------------------- */
/* LS plane-wave solution: P is the 2x3 pseudo-inverse precomputed offline
 * from the measured mic geometry (see deda/doa.py: ls_matrix). */
void deda_dir_from_tdoa(const dreal P[2][3], const dreal tau[3], const dreal coh[3],
                        deda_dir_t *out);

/* GCC-PHAT on a fractional lag grid, given the PHAT-normalised cross
 * spectrum (unit-magnitude G_k = re[k] + j im[k]) of the B selected bins and
 * their angular frequencies w[k] (rad/sample). Returns tau (samples) and the
 * coherence (peak height / B). n_lag <= DEDA_MAX_LAGS. */
#define DEDA_MAX_LAGS 64
void deda_gcc_phat_grid(const dreal *re, const dreal *im, const dreal *w, int B,
                        dreal lag0, dreal step, int n_lag, dreal *tau, dreal *coh);

#endif
