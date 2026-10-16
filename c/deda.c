/* DEDA decision core - see deda.h. Mirrors python/deda/policy.py exactly. */
#include "deda.h"

#include <math.h>
#include <string.h>

#define RAD(x) ((x) * (dreal)0.017453292519943295)
#define DEG(x) ((x) * (dreal)57.29577951308232)
#define BIG_NEG ((dreal)-1e9)

static const uint8_t QUAD_MASK[4] = {DEDA_MOTOR_FRONT, DEDA_MOTOR_RIGHT, DEDA_MOTOR_BACK, DEDA_MOTOR_LEFT};

void deda_default_config(deda_config_t *c) {
    static const dreal hh[4] = {2.0, 2.2, 2.4, 2.0}, hl[4] = {1.6, 1.8, 2.0, 1.6},
                       hu[4] = {3.0, 3.0, 3.2, 3.0};
    memset(c, 0, sizeof *c);
    c->hop_ms = 64; c->deadline_ms = 300; c->proc_ms = 60;
    c->p_open = 0.35; c->clip = 4.0; c->kappa = 0.6;
    for (int i = 0; i < 4; i++) { c->h_hi[i] = hh[i]; c->h_lo[i] = hl[i]; c->h_urgent[i] = hu[i]; }
    c->margin = 0.5; c->h_reject = -1.0;
    c->rho_min = 0.30; c->rho_strong = 0.50; c->closure_max = 0.75;
    c->norm_lo = 0.6; c->norm_hi = 1.4; c->r_min = 0.75; c->beta_min = 10.0;
    c->p_off = 0.20; c->m_off = 3; c->t_max_ms = 8000; c->move_deg = 60;
    c->upd_gap_ms = 1000; c->upd_alpha = 0.5; c->gamma_spatial = 0.0;
    c->use_dir_reliability = 1; c->sequential = 1; c->fallback_nondir = 1; c->wait_for_dir = 1;
}

static dreal pymod(dreal a, dreal m) { /* Python-style modulo, result in [0, m) */
    dreal r = (dreal)fmod(a, m);
    if (r < 0) r += m;
    return r;
}

dreal deda_wrap180(dreal a) {
    dreal r = pymod(a + 180, 360) - 180;
    return (r == (dreal)-180) ? (dreal)180 : r;
}

static dreal circ_dist(dreal a, dreal b) { return (dreal)fabs(deda_wrap180(a - b)); }

uint8_t deda_motors_for_angle(dreal theta, dreal beta_min) {
    int q = ((int)floor(pymod(theta, 360) / 90 + (dreal)0.5)) % 4;
    dreal off = deda_wrap180(theta - (dreal)(90 * q));
    dreal margin = 45 - (dreal)fabs(off);
    if (margin >= beta_min) return QUAD_MASK[q];
    int nb = (q + (off > 0 ? 1 : 3)) % 4;
    return (uint8_t)(QUAD_MASK[q] | QUAD_MASK[nb]);
}

static dreal logit_clip(dreal p, dreal clip) {
    if (p < (dreal)1e-6) p = (dreal)1e-6;
    if (p > (dreal)(1 - 1e-6)) p = (dreal)(1 - 1e-6);
    dreal l = (dreal)log(p / (1 - p));
    return l > clip ? clip : (l < -clip ? -clip : l);
}

static int dir_valid(const deda_config_t *c, const deda_window_t *w) {
    if (!w->has_dir) return 0;
    if (!c->use_dir_reliability) return 1;
    const deda_dir_t *d = &w->dir;
    return d->coherence >= c->rho_min && d->closure <= c->closure_max &&
           d->norm >= c->norm_lo && d->norm <= c->norm_hi;
}

static void reset_episode(deda_state_t *s) {
    s->open = 0; s->k = 0; s->n_dir = 0; s->latched = -1;
    for (int i = 0; i < DEDA_NCRIT; i++) s->L[i] = 0;
    s->Rx = s->Ry = s->W = s->max_coh = 0;
}

void deda_init(deda_state_t *s, const deda_config_t *c) {
    memset(s, 0, sizeof *s);
    s->cfg = *c;
    int K = 0;
    if (c->sequential) {
        K = (int)floor((c->deadline_ms - c->proc_ms) / c->hop_ms) - 1;
        if (K < 0) K = 0;
    }
    s->K = (uint8_t)K;
    reset_episode(s);
}

/* ---------------------------------------------------------- suppression */
static void track_start(deda_state_t *s, int c, dreal t, uint8_t motors, int has_theta, dreal theta) {
    deda_track_t *tr = &s->tr[c];
    memset(tr, 0, sizeof *tr);
    tr->active = 1; tr->t_alert = t; tr->last_motors = motors;
    tr->has_theta = (uint8_t)has_theta; tr->last_theta = theta; tr->t_upd = t;
    if (has_theta) { tr->ex = (dreal)sin(RAD(theta)); tr->ey = (dreal)cos(RAD(theta)); tr->ew = 1; }
    tr->order = s->next_order++;
}

static int suppressor_step(deda_state_t *s, const deda_window_t *w, deda_alert_t *out) {
    const deda_config_t *c = &s->cfg;
    int n = 0;
    /* visit active tracks in insertion order (matches the reference) */
    int idx[DEDA_NCRIT], m = 0;
    for (int i = 0; i < DEDA_NCRIT; i++) if (s->tr[i].active) idx[m++] = i;
    for (int a = 1; a < m; a++) {               /* insertion sort, m <= 4 */
        int v = idx[a], b = a - 1;
        while (b >= 0 && s->tr[idx[b]].order > s->tr[v].order) { idx[b + 1] = idx[b]; b--; }
        idx[b + 1] = v;
    }
    for (int j = 0; j < m; j++) {
        int cls = idx[j];
        deda_track_t *tr = &s->tr[cls];
        dreal p = w->probs[cls];
        tr->below = (p < c->p_off) ? (uint8_t)(tr->below + 1) : 0;
        if (tr->below >= c->m_off || w->t_ms - tr->t_alert >= c->t_max_ms) { tr->active = 0; continue; }
        if (p < c->p_open || !dir_valid(c, w)) continue;
        dreal th = RAD(w->dir.theta_deg), al = c->upd_alpha;
        tr->ex = (1 - al) * tr->ex + al * (dreal)sin(th);
        tr->ey = (1 - al) * tr->ey + al * (dreal)cos(th);
        tr->ew = (1 - al) * tr->ew + al;
        dreal r = (dreal)hypot(tr->ex, tr->ey) / (tr->ew > (dreal)1e-9 ? tr->ew : (dreal)1e-9);
        if (r < c->r_min || w->t_ms - tr->t_upd < c->upd_gap_ms) continue;
        dreal theta = pymod(DEG((dreal)atan2(tr->ex, tr->ey)), 360);
        if (!tr->has_theta || circ_dist(theta, tr->last_theta) >= c->move_deg) {
            uint8_t mm = deda_motors_for_angle(theta, c->beta_min);
            deda_alert_t *A = &out[n++];
            A->t_ms = w->t_ms; A->kind = DEDA_ALERT_UPDATE; A->cls = (uint8_t)cls; A->motors = mm;
            A->has_theta = 1; A->theta = theta; A->k = -1;
            tr->has_theta = 1; tr->last_theta = theta; tr->last_motors = mm; tr->t_upd = w->t_ms;
        }
    }
    return n;
}

/* ------------------------------------------------------------ direction */
static void add_dir(deda_state_t *s, const deda_window_t *w) {
    if (!dir_valid(&s->cfg, w)) return;
    dreal wt = s->cfg.use_dir_reliability ? w->dir.coherence : (dreal)1;
    dreal th = RAD(w->dir.theta_deg);
    s->Rx += wt * (dreal)sin(th);
    s->Ry += wt * (dreal)cos(th);
    s->W += wt;
    s->n_dir++;
    if (w->dir.coherence > s->max_coh) s->max_coh = w->dir.coherence;
}

static int dir_decision(const deda_state_t *s, dreal *theta, uint8_t *motors) {
    const deda_config_t *c = &s->cfg;
    *motors = DEDA_MOTORS_ALL; *theta = 0;
    if (s->n_dir == 0) return 0;
    if (s->n_dir == 1 && c->use_dir_reliability && s->max_coh < c->rho_strong) return 0;
    dreal r = (dreal)hypot(s->Rx, s->Ry) / (s->W > (dreal)1e-9 ? s->W : (dreal)1e-9);
    if (r < c->r_min) return 0;
    *theta = pymod(DEG((dreal)atan2(s->Rx, s->Ry)), 360);
    *motors = deda_motors_for_angle(*theta, c->beta_min);
    return 1;
}

static void emit(deda_state_t *s, const deda_window_t *w, int cls, int dir_ok, dreal theta,
                 uint8_t motors, deda_alert_t *A) {
    A->t_ms = w->t_ms; A->kind = dir_ok ? DEDA_ALERT_DIR : DEDA_ALERT_NONDIR;
    A->cls = (uint8_t)cls; A->motors = dir_ok ? motors : DEDA_MOTORS_ALL;
    A->has_theta = (uint8_t)dir_ok; A->theta = dir_ok ? theta : 0; A->k = (int8_t)s->k;
    track_start(s, cls, w->t_ms, A->motors, dir_ok, A->theta);
    reset_episode(s);
}

/* ----------------------------------------------------------------- step */
int deda_step(deda_state_t *s, const deda_window_t *w, deda_alert_t *out) {
    const deda_config_t *c = &s->cfg;
    int n = suppressor_step(s, w, out);
    int cand[DEDA_NCRIT], nc = 0;
    for (int i = 0; i < DEDA_NCRIT; i++) if (!s->tr[i].active) cand[nc++] = i;

    if (!s->open) {
        dreal pm = -1;
        for (int j = 0; j < nc; j++) if (w->probs[cand[j]] > pm) pm = w->probs[cand[j]];
        if (nc == 0 || pm < c->p_open) return n;
        s->open = 1; s->k = 0;
    } else {
        s->k++;
    }
    const int K = s->K;

    dreal gain = (s->k == 0) ? (dreal)1 : c->kappa;
    for (int i = 0; i < DEDA_NCRIT; i++) {
        if (!s->tr[i].active) s->L[i] += gain * logit_clip(w->probs[i], c->clip);
        else s->L[i] = BIG_NEG;
    }
    add_dir(s, w);

    dreal th; uint8_t mm;
    if (s->latched >= 0) {
        int ok = dir_decision(s, &th, &mm);
        if (ok || s->k >= K) {
            if (ok || c->fallback_nondir) emit(s, w, s->latched, ok, th, mm, &out[n++]);
            else reset_episode(s);
        }
        return n;
    }
    if (nc == 0) { reset_episode(s); return n; }

    int cs = cand[0];
    for (int j = 1; j < nc; j++) if (s->L[cand[j]] > s->L[cs]) cs = cand[j];
    dreal runner = BIG_NEG;
    for (int j = 0; j < nc; j++) if (cand[j] != cs && s->L[cand[j]] > runner) runner = s->L[cand[j]];
    dreal frac = K > 0 ? (dreal)s->k / (dreal)K : (dreal)1;
    dreal h = c->h_hi[cs] - (c->h_hi[cs] - c->h_lo[cs]) * frac;
    int ok = dir_decision(s, &th, &mm);
    if (!ok && c->gamma_spatial > 0 && s->k < K) h += c->gamma_spatial;
    int accepted = s->L[cs] >= h && (s->L[cs] - runner) >= c->margin;

    if (accepted) {
        if (ok) emit(s, w, cs, 1, th, mm, &out[n++]);
        else if (c->wait_for_dir && s->k < K && s->L[cs] < c->h_urgent[cs]) s->latched = (int8_t)cs;
        else if (c->fallback_nondir) emit(s, w, cs, 0, 0, DEDA_MOTORS_ALL, &out[n++]);
        else reset_episode(s);
        return n;
    }
    dreal Lmax = BIG_NEG;
    for (int j = 0; j < nc; j++) if (s->L[cand[j]] > Lmax) Lmax = s->L[cand[j]];
    if (Lmax <= c->h_reject || s->k >= K) reset_episode(s);
    return n;
}
