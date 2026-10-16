/*
 * Integration example: where DEDA sits in the SoundScape Band firmware loop.
 *
 * STATUS: illustrative, NOT compiled or tested on hardware. The functions
 * marked "platform" must be written for your board (RP2040 Pico SDK / ESP-IDF
 * / Arduino). Only deda_* functions come from ../c and are tested on a PC.
 */
#include <math.h>
#include <stdint.h>

#include "deda.h"

/* ---- calibration (fill from python/evaluate_logs.py output) ------------- */
static const float T_CAL = 1.0f;          /* temperature */
static const dreal P[2][3] = {            /* pseudo-inverse from measured mic positions */
    {0.0f, 0.0f, 0.0f},                   /* compute with deda.doa.ls_matrix(pos, fs) */
    {0.0f, 0.0f, 0.0f},
};

/* ---- platform functions (to be implemented) ----------------------------- */
uint32_t now_ms(void);
int  audio_wait_hop(void);                                   /* blocks until next hop is buffered */
int  doa_compute(float tau[3], float coh[3]);                /* Path A; returns 0 if invalid */
int  classifier_logits(float logits[DEDA_NCLS]);             /* Path B; returns 0 on overrun */
void haptics_play(uint8_t motors, uint8_t cls, uint8_t kind);/* PWM patterns */

static void softmax_T(const float *z, float T, dreal *p) {
    float m = z[0], s = 0.0f, e[DEDA_NCLS];
    for (int i = 1; i < DEDA_NCLS; i++) if (z[i] > m) m = z[i];
    for (int i = 0; i < DEDA_NCLS; i++) { e[i] = expf((z[i] - m) / T); s += e[i]; }
    for (int i = 0; i < DEDA_NCLS; i++) p[i] = e[i] / s;
}

void deda_task(void) {
    deda_config_t cfg;
    deda_default_config(&cfg);
    /* cfg.h_hi[...] = ...;  copy calibrated thresholds here */
    /* cfg.sequential = 0;   if MFCC+CNN per hop exceeds ~60 ms */

    deda_state_t st;
    deda_init(&st, &cfg);
    deda_alert_t out[DEDA_MAX_ALERTS_PER_STEP];

    for (;;) {
        if (!audio_wait_hop()) continue;

        float logits[DEDA_NCLS];
        if (!classifier_logits(logits)) continue;          /* overrun: skip, never queue */

        deda_window_t w;
        w.t_ms = (dreal)now_ms();
        softmax_T(logits, T_CAL, w.probs);

        float tau_f[3], coh_f[3];
        w.has_dir = (uint8_t)doa_compute(tau_f, coh_f);
        if (w.has_dir) {
            dreal tau[3] = {tau_f[0], tau_f[1], tau_f[2]};
            dreal coh[3] = {coh_f[0], coh_f[1], coh_f[2]};
            deda_dir_from_tdoa(P, tau, coh, &w.dir);
        }

        int n = deda_step(&st, &w, out);
        for (int i = 0; i < n; i++)
            haptics_play(out[i].motors, out[i].cls, out[i].kind);
    }
}
