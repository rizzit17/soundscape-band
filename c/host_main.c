/* Host test driver: reads windows from stdin (CSV, no header):
 *   t_ms,p0,p1,p2,p3,p4,has_dir,theta,closure,norm,coh
 * optional first line "#CFG use_dir_reliability sequential fallback wait gamma"
 * writes alerts to stdout: t_ms,kind,cls,motors,k
 * Mode "gcc": reads B, lag0, step, n_lag then B lines re,im,w; prints tau,coh. */
#include <stdio.h>
#include <string.h>

#include "deda.h"

static int run_gcc(void) {
    int B, n_lag; double lag0, step;
    if (scanf("%d %lf %lf %d", &B, &lag0, &step, &n_lag) != 4) return 1;
    static dreal re[4096], im[4096], w[4096];
    for (int k = 0; k < B; k++) { double a, b, c; if (scanf("%lf,%lf,%lf", &a, &b, &c) != 3) return 1; re[k] = a; im[k] = b; w[k] = c; }
    dreal tau, coh;
    deda_gcc_phat_grid(re, im, w, B, (dreal)lag0, (dreal)step, n_lag, &tau, &coh);
    printf("%.6f,%.6f\n", (double)tau, (double)coh);
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "gcc") == 0) return run_gcc();
    if (argc > 1 && strcmp(argv[1], "sizes") == 0) {
        printf("sizeof(deda_state_t)=%zu sizeof(deda_config_t)=%zu sizeof(dreal)=%zu\n",
               sizeof(deda_state_t), sizeof(deda_config_t), sizeof(dreal));
        return 0;
    }
    deda_config_t cfg; deda_default_config(&cfg);
    char line[512];
    deda_state_t st; int inited = 0;
    deda_alert_t out[DEDA_MAX_ALERTS_PER_STEP];
    while (fgets(line, sizeof line, stdin)) {
        if (line[0] == '#') {
            int a, b, c, d; double g;
            if (sscanf(line, "#CFG %d %d %d %d %lf", &a, &b, &c, &d, &g) == 5) {
                cfg.use_dir_reliability = (uint8_t)a; cfg.sequential = (uint8_t)b; cfg.fallback_nondir = (uint8_t)c;
                cfg.wait_for_dir = (uint8_t)d; cfg.gamma_spatial = g;
            }
            continue;
        }
        if (!inited) { deda_init(&st, &cfg); inited = 1; }
        deda_window_t w; double v[11]; int hd;
        if (sscanf(line, "%lf,%lf,%lf,%lf,%lf,%lf,%d,%lf,%lf,%lf,%lf", &v[0], &v[1], &v[2], &v[3], &v[4],
                   &v[5], &hd, &v[7], &v[8], &v[9], &v[10]) != 11) continue;
        w.t_ms = v[0];
        for (int i = 0; i < 5; i++) w.probs[i] = v[1 + i];
        w.has_dir = (uint8_t)hd;
        w.dir.theta_deg = v[7]; w.dir.closure = v[8]; w.dir.norm = v[9]; w.dir.coherence = v[10];
        int n = deda_step(&st, &w, out);
        for (int i = 0; i < n; i++)
            printf("%.3f,%d,%d,%d,%d\n", (double)out[i].t_ms, out[i].kind, out[i].cls, out[i].motors, out[i].k);
    }
    return 0;
}
