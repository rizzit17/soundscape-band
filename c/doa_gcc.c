/* Direction front-end helpers - see deda.h.
 * The FFTs themselves should come from CMSIS-DSP (arm_rfft_fast_f32 on the
 * RP2040 / ESP-DSP on the ESP32); this file only contains the parts that are
 * specific to this design. */
#include "deda.h"

#include <math.h>

void deda_dir_from_tdoa(const dreal P[2][3], const dreal tau[3], const dreal coh[3], deda_dir_t *out) {
    dreal vx = P[0][0] * tau[0] + P[0][1] * tau[1] + P[0][2] * tau[2];
    dreal vy = P[1][0] * tau[0] + P[1][1] * tau[1] + P[1][2] * tau[2];
    dreal th = (dreal)atan2(vx, vy) * (dreal)57.29577951308232;
    if (th < 0) th += 360;
    out->theta_deg = th;
    out->closure = (dreal)fabs(tau[0] + tau[1] + tau[2]);   /* pairs (0,1),(1,2),(2,0) */
    out->norm = (dreal)hypot(vx, vy);
    dreal m = coh[0];
    if (coh[1] < m) m = coh[1];
    if (coh[2] < m) m = coh[2];
    out->coherence = m;
}

/* R(l) = (1/B) * sum_k Re{ G_k * exp(j w_k l) }, l = lag0 + i*step.
 * Uses a per-bin phasor recurrence: one sin/cos pair per bin per call
 * (could be tabulated once at start-up) and 4 MACs per (bin, lag). */
void deda_gcc_phat_grid(const dreal *re, const dreal *im, const dreal *w, int B,
                        dreal lag0, dreal step, int n_lag, dreal *tau, dreal *coh) {
    dreal R[DEDA_MAX_LAGS];
    if (n_lag > DEDA_MAX_LAGS) n_lag = DEDA_MAX_LAGS;
    if (n_lag < 1) { *tau = 0; *coh = 0; return; }
    for (int i = 0; i < n_lag; i++) R[i] = 0;
    for (int k = 0; k < B; k++) {
        dreal c0 = (dreal)cos(w[k] * lag0), s0 = (dreal)sin(w[k] * lag0);
        dreal cs = (dreal)cos(w[k] * step), ss = (dreal)sin(w[k] * step);
        dreal pr = re[k] * c0 - im[k] * s0;   /* G_k e^{j w lag0} */
        dreal pi = re[k] * s0 + im[k] * c0;
        for (int i = 0; i < n_lag; i++) {
            R[i] += pr;
            dreal t = pr * cs - pi * ss;
            pi = pr * ss + pi * cs;
            pr = t;
        }
    }
    int best = 0;
    for (int i = 1; i < n_lag; i++) if (R[i] > R[best]) best = i;
    dreal t = lag0 + step * (dreal)(double)best;
    if (best > 0 && best < n_lag - 1) {
        dreal a = R[best - 1], b = R[best], c = R[best + 1], den = a - 2 * b + c;
        if (fabs(den) > 1e-12) t += (dreal)0.5 * (a - c) / den * step;
    }
    *tau = t;
    dreal pk = R[best] / (dreal)(double)(B > 0 ? B : 1);
    *coh = pk > 0 ? pk : 0;
}
