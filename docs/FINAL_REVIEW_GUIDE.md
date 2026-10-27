# Final review: SoundScape Lab

## Start the demonstration

Double-click `Start-Simulator.cmd` in the project folder. Keep its terminal open and open **http://127.0.0.1:8765**. The header should show **Python engine connected**. On a new computer, install Python 3.10+ and run `python -m pip install -r requirements.txt` first. See [the setup guide](SIMULATION_GUIDE.md) for an isolated environment.

The interface uses local assets and runs without internet after dependency installation. It requires the Python server; opening the HTML file directly will not work.

## Current presentation controls

Use **Hear & watch** to enable audible replay of the exact synthetic Mic 1 signal. **Presentation mode** focuses on the wearer, plain-language explanation and actual Baseline B / DEDA commands. **Next demo case** walks through the teaching cases. Use **0.25×** to inspect decisions slowly; audio pitch changes with replay speed. Key-event buttons jump to computed timestamps. Evidence bars in the full lab show accumulated scores, not percentages.

For the current session port, run `python python/simulator_server.py --port 8766` and open http://127.0.0.1:8766. The default launcher still uses 8765. Both are local-only addresses.

The [Wokwi kit](../wokwi/README.md) supplements the browser with prepared inputs processed by C DEDA, an OLED, five buttons and four pulsing LEDs. It has no live microphone recognition or measured physical vibration. Use the [updated report](submission/SoundScape_Final_Report_Updated.docx), [paper](submission/SoundScape_Final_Research_Paper_Updated.docx) and [teaching guide](PROJECT_TEACHING_GUIDE.md) for the submission.

## A four-minute walkthrough

1. **Scene explorer — Horn behind.** The initial scene is computed automatically and pauses at the first warning. Explain the true source, estimated angle, reliability checks, highlighted back motor and DEDA/baseline delays. The delay uses the simulated event onset, not page loading time.
2. **Inspect the evidence.** Use previous/next window, Play, speed or the timeline. Click a processing-trace row to inspect that exact window. Select a new direction: the settings-changed notice prevents confusing old results with a new scene. Select **Run scene** to recompute and replay the change from the beginning, respecting the mute setting.
3. **Show uncertainty.** Select **Direction dropout**: an accepted sound class produces a general four-motor warning. Select **Uncertain class** and **Ambient only**: neither preset should produce an accepted warning. **Competing sources** is a stress case; inspect errors honestly.
4. **Review checklist.** Select **Run review cases**. Five scenes run through the Python engine. Compare expected and observed behavior; select **Inspect scene** for the exact computed trace. Download **Evidence JSON**, or use **Print summary** to save a PDF from the browser print dialog. These checks are demonstrations, not an accuracy estimate.
5. **Experiments.** Run **Quick** with **1 seed**: 33 trials, including 32 critical events and one ambient control. Progress counts completed trials. Cancel stops between trials and does not publish partial metrics. Compare wrong direction, misses, general warnings and delay together. Export JSON and trial CSV.

Keep an evidence JSON and CSV from the actual demonstration. Recent scene summaries are stored in this browser only; **Restore settings** restores the seed and parameters for recomputation. They are not a shared experiment database.

## What the submission demonstrates

- Procedural source audio, three virtual microphones and the existing Python GCC-PHAT estimator.
- Computed geometric checks, the original DEDA decision policy and Baseline B on the same windows.
- Inspectable motor commands, reproducible presets, replay, comparison history and evidence exports.
- Asynchronous quick/full experiments, progress, cancellation and recovery of a running job after a page reload in the same browser tab.

Sound-class probabilities are **scripted inputs**. This web lab does not use the Android app's YAMNet classifier. It does not measure physical vibration, room acoustics, MCU latency, user performance or recognition accuracy. The 60 ms processing allowance and 300 ms target are model assumptions. The acoustic stress suite and the paper's original decision-stream benchmark are separate experiments; do not interchange their numbers.

## Verification of this revision

The Python/C regression suite passed **49 tests**; the JavaScript projection checks passed **3 tests**. Browser checks covered scene computation, exact replay stepping, stale-settings feedback, the five review cases, experiment progress and exports. The downloaded scene JSON and window CSV both contained 29 windows. All five default review behaviors matched their stated expectations on this machine.

To repeat the automated checks from the project folder:

```powershell
Push-Location python
python -m pytest tests -q
Pop-Location
node simulator/app.test.cjs
```

Node is optional for these JavaScript checks and is not needed to run the app. Without built C executables/compiler support, cross-implementation tests may skip; see the setup guide.

![Scene explorer with computed direction, reliability checks and replay](screenshots/simulator-review.jpg)

![Review checklist after computing all five cases](screenshots/simulator-checklist.jpg)
