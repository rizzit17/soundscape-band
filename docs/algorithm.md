# DEDA — algorithm specification

Dual-Evidence Deadline Alerting runs once per analysis hop **H** (default 64 ms) on the outputs of the two existing branches:

- **Path A** (direction): 3 × GCC-PHAT → fractional TDOAs τ₀₁, τ₁₂, τ₂₀ and per-pair coherences
- **Path B** (class): MFCC → 1D-CNN → logits over {horn, siren/alarm, shout, reversing beep, ambient}

It keeps at most one *evidence episode* open (≤ K+1 windows) plus one suppression record per critical class.
Reference code: [`python/deda/policy.py`](../python/deda/policy.py) and [`c/deda.c`](../c/deda.c).

![State diagram](figures/deda_state_diagram.png)

## 1. Class evidence

Calibrated posteriors (temperature T fitted on the calibration split) are turned into clipped log-odds and accumulated over the episode, which opens at window t₀ when an unsuppressed critical class has p ≥ p_open:

$$p_t(c) = \mathrm{softmax}(z_t/T)_c, \qquad \lambda_t(c) = \mathrm{clip}\left(\ln\frac{p_t(c)}{1-p_t(c)}, -L, L\right)$$

$$\Lambda_k(c) = \lambda_{t_0}(c) + \kappa\sum_{j=1}^{k}\lambda_{t_0+j}(c), \qquad K = \left\lfloor\frac{D - T_{proc}}{H}\right\rfloor - 1$$

$$h_c(k) = h_c^{hi} - (h_c^{hi} - h_c^{lo})\frac{k}{K}, \qquad \text{accept } c^\ast \iff \Lambda_k(c^\ast) \ge h_{c^\ast}(k) \wedge \Lambda_k(c^\ast) - \max_{c\ne c^\ast}\Lambda_k(c) \ge \mu$$

With D = 300 ms, T_proc = 60 ms (placeholder until measured) and H = 64 ms, **K = 2**. Λ is an empirical score, not a log-likelihood ratio (overlapping windows are correlated), so thresholds are chosen on calibration data.

## 2. Direction evidence

For a plane wave from unit direction **u** and mic positions **m**ᵢ:

$$\tau_{ij} = -\frac{f_s}{c}(\mathbf{m}_i - \mathbf{m}_j)^\top\mathbf{u}, \qquad \boldsymbol\tau = \mathbf{A}\mathbf{u}, \qquad \mathbf{v} = \mathbf{P}\boldsymbol\tau\ (\mathbf{P} = \mathbf{A}^+)$$

GCC-PHAT is evaluated on a 0.25-sample lag grid over the physically possible range, using only the strongest 25 % of cross-power bins in 300 Hz–6 kHz.

Per window: azimuth θ = atan2(v_x, v_y) (clockwise from front), norm ν = ‖**v**‖, closure e = |τ₀₁ + τ₁₂ + τ₂₀|, coherence ρ = min pairwise PHAT peak.

- **Closure** is the single redundancy of a 3-mic planar array: it is zero for any single source. Large e ⇒ pairs locked onto different sources, a reflection or a noise peak.
- **Norm** catches what closure cannot: a constant capture offset on one microphone (it cancels around the loop but pushes **v** off the unit circle).

$$V_t = [\rho_t \ge \rho_{min}][e_t \le e_{max}][\nu_{lo} \le \nu_t \le \nu_{hi}]$$

$$\mathbf{R}_k = \sum_{j\le k} V_j\rho_j(\sin\theta_j, \cos\theta_j), \quad r_k = \|\mathbf{R}_k\| / \sum_{j\le k} V_j\rho_j, \quad \mathrm{conf}_k = [n_k\ge1][n_k>1 \vee \rho_{max}\ge\rho_{strong}][r_k\ge r_{min}]$$

Unit-vector averaging means 350° and 10° average to 0°, and opposite estimates give r ≈ 0 (refused).

**Motors:** q = ⌊θ̂/90° + ½⌋ mod 4 (0 front, 1 right, 2 back, 3 left). If the estimate is within β_min of a quadrant boundary, drive q and its nearer neighbour.

## 3. Decision at episode step k

| Condition | Action |
|---|---|
| class accepted and direction confident | **DIR alert** (class c\*, motors from θ̂) |
| class accepted, no confident direction, k < K and Λ < h_urgent | **wait**: class latched, collect direction only |
| class accepted, no confident direction, k = K or Λ ≥ h_urgent | **NONDIR alert**: all four motors, class pattern |
| latched and a later window gives a confident direction | DIR alert |
| not accepted and (max Λ ≤ h_reject or k = K) | **reject** |
| otherwise | next window |

**After an alert:** the class is suppressed until p < p_off for m_off windows, or t_max (8 s) passes (reminder for a persistent hazard). During suppression an EMA of valid directions sends an **UPDATE** pulse if the source moves ≥ 60°, or to refine an earlier NONDIR alert (max once per second).

Optional (hypothesis H3, default off): raise the class threshold by γ while no confident direction exists and k < K.

## 4. Pseudocode

```text
DEDA_STEP(window w = (t, p[0..4], dir or NONE)):
  alerts ← SUPPRESSOR_STEP(w)
  cand ← critical classes not suppressed
  if no episode open:
      if cand empty or max p[c∈cand] < p_open: return alerts
      open episode; k ← 0
  else k ← k + 1
  for c in cand: Λ[c] += (1 if k = 0 else κ)·clip(logit p[c], −L, L)
  if VALID(w.dir): R += ρ·(sin θ, cos θ); W += ρ; n += 1
  (conf, θ̂, S) ← DIRECTION_DECISION(R, W, n)
  if latched ≠ NONE:
      if conf: emit DIR(latched, S)   elif k = K: emit NONDIR(latched)
      return alerts
  c* ← argmax Λ over cand;  h ← h_hi[c*] − (h_hi[c*] − h_lo[c*])·k/K
  if Λ[c*] ≥ h and Λ[c*] − max_{c≠c*} Λ[c] ≥ μ:
      if conf:                               emit DIR(c*, S)
      elif k < K and Λ[c*] < h_urgent[c*]:   latched ← c*
      else:                                  emit NONDIR(c*)
  elif max Λ ≤ h_reject or k = K: close episode
  return alerts
```

## 5. Parameters

| Parameter | Default | Selected by |
|---|---|---|
| H, D, T_proc | 64 ms, 300 ms, 60 ms | H > measured MFCC+CNN time per hop; T_proc = measured onset-to-motor time |
| K | 2 | Derived |
| T | fitted | Min NLL on calibration split |
| p_open, L, κ | 0.35, 4, 0.6 | p_open: ≥ 99 % of calibration events open an episode; κ sensitivity 0.4–1.0 |
| h_hi, h_lo (per class) | 2.0–2.4, 1.6–2.0 | Grid search: fewest false alerts/h s.t. missed-or-late ≤ 5 % per class |
| h_urgent, μ, h_reject | h_hi+1, 0.5, −1.0 | Fixed offset; calibration confusion matrix |
| ρ_min, ρ_strong, e_max | 0.30, 0.50, 0.75 sample | ROC knee: correct- vs wrong-quadrant calibration windows |
| ν_lo, ν_hi, r_min, β_min | 0.6, 1.4, 0.75, 10° | Measured on the worn band (body shadowing shifts ν) |
| p_off, m_off, t_max | 0.2, 3, 8 s | Event-end behaviour on calibration recordings |
| move threshold, update gap | 60°, 1 s | Fixed |

## 6. Cost

- DEDA per window: ~4 log, ≤ 10 sin/cos, ≤ 5 atan2/hypot, a few hundred flops; constant in stream length.
- State: 312 B; config: 140 B (host, float build).
- GCC grid (3 pairs, top-25 % bins, 0.25-sample grid): ≈ 18.6 k complex MACs/window at 16 kHz, ≈ 30 k at 48 kHz.
- On the RP2040 (no FPU) run the GCC grid in Q15/Q31; on the ESP32 float is fine.
