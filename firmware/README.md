# Firmware

> **Status: not yet implemented on hardware.** The C core in [`../c`](../c) is tested on a PC only. This folder contains an integration example showing where DEDA plugs into the existing pipeline. Nothing here has been compiled for the RP2040 or ESP32 yet.

## Pipeline per hop (H = 64 ms)

```
I²S DMA (3 mics, synchronous) ──► ring buffer
        │
        ├─ Path A: 3 × rFFT → PHAT cross-spectra (top 25 % bins) → deda_gcc_phat_grid() ×3
        │          → deda_dir_from_tdoa()  → angle, closure, norm, coherence
        │
        └─ Path B: MFCC → TFLite Micro 1D-CNN (INT8) → logits → softmax(z / T)
                         │
                         ▼
                   deda_step()  ──► alerts ──► haptics (4 PWM motors)
```

## Suggested project layout (PlatformIO)

```
firmware/
├── platformio.ini
├── src/
│   ├── main.cpp            # capture loop, calls Path A, Path B, DEDA, haptics
│   ├── audio_i2s.cpp       # synchronous 3-mic capture (PIO on RP2040 / dual I2S on ESP32)
│   ├── doa_frontend.cpp    # rFFT + PHAT + deda_gcc_phat_grid
│   ├── classifier.cpp      # MFCC + TFLite Micro model
│   └── haptics.cpp         # patterns per class / NONDIR / UPDATE
├── lib/deda/               # copy of ../c/deda.c, deda.h, doa_gcc.c
└── include/calibration.h   # T, thresholds, matrix P (from calibration data)
```

## Steps to bring up

1. **Capture:** record a click from 0°/90°/180°/270° and confirm the three channels are synchronous (closure ≈ 0, norm ≈ 1).
2. **Measure timing first:** time MFCC + CNN per hop with a GPIO toggle. If it exceeds ~60 ms, set `cfg.sequential = 0` (K = 0) or lengthen the hop.
3. **Calibrate:** log windows in the [`data/`](../data/README.md) format, run `python/evaluate_logs.py`, and copy the fitted temperature and thresholds into `calibration.h`.
4. **Integrate DEDA** as in [`deda_integration_example.c`](deda_integration_example.c).
5. **Measure** RAM, flash, per-hop time and onset-to-vibration latency (Table R3 in [`docs/experiment_protocol.md`](../docs/experiment_protocol.md)).
