# Data

This folder holds **formats only**. Raw recordings are too large for Git and may contain voices, so they should be published on Zenodo (or kept private) and linked here.

> If recordings include people's voices (e.g. the "shout" class), get consent from everyone recorded before publishing them.

## `windows.csv` — one row per analysis window

| Column | Meaning |
|---|---|
| `session` | recording session ID (the unit of splitting and bootstrapping) |
| `split` | `calib` or `test` — assigned per session and source clip, never per window |
| `t_ms` | end time of the window within the session (ms) |
| `l_horn`, `l_siren`, `l_shout`, `l_beep`, `l_ambient` | **raw** CNN logits (temperature is fitted by `evaluate_logs.py`) |
| `theta` | azimuth, degrees clockwise from front; empty if DOA missing |
| `closure` | \|τ₀₁ + τ₁₂ + τ₂₀\| in samples; empty if missing |
| `norm` | ‖P τ‖; empty if missing |
| `coh` | minimum pairwise PHAT coherence, 0–1; empty if missing |

## `events.csv` — ground truth, one row per played sound

| Column | Meaning |
|---|---|
| `session` | matches `windows.csv` |
| `onset_ms`, `offset_ms` | acoustic onset/offset within the session (from the reference microphone) |
| `cls` | `horn`, `siren`, `shout` or `beep` |
| `theta` | true azimuth (0, 90, 180, 270) |
| `distance_m` | 1, 3 or 5 |
| `noise` | `quiet`, `babble`, `traffic` |

Ambient-only sessions have rows in `windows.csv` and none in `events.csv`.

## Example

```bash
cd python
python make_demo_logs.py            # writes demo_windows.csv / demo_events.csv (synthetic)
python evaluate_logs.py demo_windows.csv demo_events.csv --target-miss 0.2
```

## Recordings

Zenodo DOI: _to be added_
