# SoundScape Band simulation guide

You can complete and demonstrate the software prototype without microphones, a microcontroller or vibration motors. The browser application runs the repository's Python direction estimator and DEDA algorithm. It generates virtual microphone signals and displays the resulting motor commands.

Sound classification is currently represented by explicitly simulated probabilities. This guide completes the acoustic simulation and alert-policy demonstration; it does not claim automatic recognition of real recordings or a finished physical wearable.

## 1 Open the project

Open PowerShell or the VS Code terminal and enter:

```powershell
cd C:\Users\Rishit\Desktop\PROJECTS\soundscape-band
python --version
```

Use Python 3.10 or newer. Your current computer already has Python and the required libraries. You do not need React, Node.js, Wokwi, an Arduino IDE or a paid service to run this version.

## 2 Install dependencies on a new computer

For an isolated installation, run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

You do not need to activate the environment or change PowerShell's execution policy. Wherever this guide uses `python`, you can use `.\.venv\Scripts\python.exe` instead. The Windows launcher automatically uses that environment if present.

Internet is needed for installing dependencies. The browser demonstration itself has no remote assets or service dependencies.

## 3 Start the browser application

From the project root:

```powershell
python python\simulator_server.py
```

Open **http://127.0.0.1:8765** in your browser. Keep the terminal open. The header should say **Python engine connected**.

You can also double-click `Start-Simulator.cmd`, then open that address. Press Ctrl+C in the terminal to stop the server. Do not open `simulator/index.html` directly: it needs the Python server to calculate results.

## 4 Understand what is happening

1. Select a sound surrogate and its true angle around the virtual wearer.
2. Python generates the source waveform with a known event onset at 192 ms.
3. The existing free-field model creates three microphone recordings for a 35 mm triangular array. Independent white noise is added at the selected active-source SNR.
4. GCC-PHAT estimates three arrival-time differences and derives an angle. Strongest-bin selection defaults to 25%.
5. Closure, plane-wave norm and PHAT coherence are computed from those microphone signals. Their values are not selected by a reliability checkbox.
6. A deliberately scripted sound-class probability stream is supplied to DEDA. The confidence slider controls it; this is not a CNN prediction.
7. The original DEDA policy chooses a directional warning, general warning, update, wait or rejection. Baseline B receives exactly the same windows.
8. The browser replays the computed outputs. Four highlighted circles represent the last commanded motors; the visual stays lit so the audience can inspect it. It is not a simulated motor pulse or physical vibration.

Direction uses the wearer's frame: **0° front, 90° right, 180° back, 270° left**. A source near a quadrant boundary can activate two neighboring motors.

## 5 Demonstrate the main scenarios

Use the preset buttons above the workspace. Each preset resets the seed, duration and strongest-bin setting so it is reproducible. The initial scene computes automatically and pauses at its first warning. For a concise presentation sequence, use the [final review guide](FINAL_REVIEW_GUIDE.md).

| Preset | What to show | Explanation |
| --- | --- | --- |
| Horn behind | Back motor; seed 7 first alert at 320 ms, or 128 ms after sound onset | Python estimates the direction independently of the selected true angle |
| Siren left | Left motor; seed 7 first alert 64 ms after sound onset | A reliable estimate permits a directional warning |
| Direction dropout | All four motors; seed 7 warning 192 ms after onset | Explicit fault injection removes the direction observation before policy processing |
| Uncertain class | No accepted warning at score 0.30 | Direction alone cannot substitute for accepted class evidence |
| Ambient only | No alert | Scripted probabilities favor ambient; this does not measure classifier performance |
| Competing sources | Inspect raw angles, reliability and both policies | Two sources can fool the reliability checks; do not promise that DEDA always selects the true source |

Run a preset, then replay at 0.5× or pause and scrub the timeline. Inspect a window during the sound, not just the ambient tail. The source starts at 192 ms; the 1024 ms preset sound ends at 1216 ms.

The measured values on your machine may differ slightly with numerical library versions. They are calculated anew, not hardcoded expected results.

### A useful additional demonstration

Select **Reversing beep**, angle 0°, SNR 20 dB, seed 7. A narrowband signal can make direction ambiguous even without room reflections. The model may issue a general warning. Explain why fallback is a valid result rather than forcing the front motor to light up.

Lower class confidence and shorten the event to 64 ms in Reproducibility settings. A short or weak event can be missed: the deadline does not guarantee recognition of every sound. A reliable direction alone cannot substitute for accepted sound-class evidence.

## 6 Export a single demonstration

After running a scene:

- **Run JSON** downloads the scenario settings, complete policy configuration, per-window direction checks, class probabilities and alert lists.
- **Window CSV** downloads a table you can open in Excel or analyze in Python.

The browser saves these to your normal Downloads location. Its replay time does not alter the computed export. Re-running with the same settings and seed reproduces the numerical trace; laptop computation time can vary.

## 7 Run a new experiment

Open **Experiments** in the browser. Start with **Quick** and **1 seed**, then click **Run experiment**. The progress bar counts completed trials. **Cancel** finishes the current trial and discards the incomplete result; it does not publish partial rates. Reloading the same tab reconnects to its running job while the Python server remains active. Only the latest job is retained in server memory, so download completed evidence before starting another job or restarting the server.

| Suite | Coverage per seed |
| --- | --- |
| Quick | 2 sound surrogates × 4 angles × 2 SNR levels × 2 conditions = 32 critical trials, plus 1 ambient trial |
| Full | 4 sound surrogates × 4 angles × 3 SNR levels × 4 conditions = 192 critical trials, plus 1 ambient trial |

Quick SNRs: 20 and 0 dB. Full adds −10 dB. Full conditions are free field, competing source, a +3-sample timing fault on mic 3, and one simplified reflection. The source event lasts 384 ms in the experiment suite. The scripted confidence varies among 65%, 80% and 95% by seed and angle; this is an assumption, not a measured classifier accuracy. There is no distance factor in this free-field experiment.

The policies reset for each trial. DEDA uses its default configuration, including the existing 60 ms assumed processing allowance. Baseline B uses threshold 0.70. Neither policy is tuned on the test results. These fixed defaults are uncalibrated and this comparison does not establish superiority at matched sensitivity.

Read all results together:

- **Wrong-direction rate:** critical events whose first directional warning excludes the true quadrant, divided by all critical events.
- **Missed rate:** critical events with no associated first warning.
- **Missed or late rate:** missed events or first warnings later than 300 ms after source onset.
- **General warning fraction:** non-directional first warnings divided by detected events.
- **p50 and p95 alert delay:** percentiles among detected events, on the simulated clock. Misses are reported separately.
- **False alerts per ambient hour:** calculated from the ambient-only control trials. Those trials are very short and have scripted ambient probabilities without confusers, so a zero is not evidence of effective real-world false-alarm rejection.

First warnings are associated from onset to event end + 500 ms, matching the repository's event-association convention. Direction updates do not count as first detections. A motor set containing the true quadrant counts as correct; all-motor fallback is reported separately, not treated as a directional success.

Export **JSON** and **Trial CSV** to preserve the settings and individual outcomes. Report cases where DEDA loses as well as those where it helps.

## 8 Save results and graphs from PowerShell

For automatic JSON, CSV and a PNG comparison chart:

```powershell
python python\run_simulator_experiment.py --suite quick --seeds 2
python python\run_simulator_experiment.py --suite full --seeds 5
```

Each command creates a fresh timestamped folder under `results/simulation/` containing:

```text
experiment.json
trials.csv
comparison.png
README.txt
```

These files are new acoustic stress-test results. They do not replace `results/synthetic_results.json`, the original paper benchmark. Generated output folders are ignored by Git.

## 9 Reproduce the original paper experiments separately

The paper compares policies on generated decision streams, not on this newly connected acoustic pipeline. To rerun its original code:

```powershell
python python\acoustic_checks.py
python python\run_synthetic.py
```

`acoustic_checks.py` prints direction-estimation checks. `run_synthetic.py` runs four 20-minute test streams and separate calibration streams, with multiple policy variants and threshold sweeps. It can take considerably longer than the browser suite and overwrites the original `results/synthetic_results.json` and `results/synthetic_tradeoff.png`; copy those two files to a separate folder first if you want to preserve them.

Keep the two experiment types distinct in your report. Do not copy the reported 23.5% and 2.7% into the new suite or tune its parameters until those numbers appear.

## 10 Verify Python and C

The browser only needs Python. If GCC or Clang is installed, you can additionally build and check the host C implementation:

```powershell
python python\build_c.py
cd python
python -m pytest -q -p no:cacheprovider tests
cd ..
```

Without a C compiler/build, eight cross-implementation tests skip; that does not prevent browser simulation. The C executables run on your computer, not on an ESP32 or RP2040.

If unrelated globally installed pytest plugins cause shutdown issues, retry in a fresh terminal with:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -m pytest -q -p no:cacheprovider python\tests
```

## 11 Use Google Colab if you need a shareable notebook

Colab is optional. It runs the same algorithms; it is not a second source of independent validation.

1. Run `python python\package_simulation.py` locally. It prints the path of a new source ZIP under `results/simulation/`.
2. Go to **https://colab.research.google.com/** and select **File → Upload notebook**.
3. Open `notebooks/SoundScape_Simulation.ipynb` from this project.
4. Run the first code cell and select the ZIP you just generated. Only that source bundle is uploaded; the packaging script excludes recordings, Git history, binaries and saved results.
5. Run the setup cell, then the single-scene and experiment cells in order.
6. Download the generated results ZIP from the final cell.

The notebook uses the uploaded local source instead of assuming your GitHub repository already contains these changes. The local browser interface is the presentation tool; the notebook reproduces numerical experiments and plots. You do not need a tunnel or public server.

## 12 Present the work accurately

Suggested opening:

> We developed a simulation-based software prototype of SoundScape Band. We generate signals for three virtual microphones, estimate source direction using GCC-PHAT, check its reliability and run our DEDA decision algorithm. The four indicators show the motor commands the proposed wearable would receive. Sound-class probabilities are simulated inputs; physical hardware, trained audio recognition and user trials are future work.

For a five-minute demo:

1. Explain the problem and the three-microphone/four-motor design.
2. Show the horn and siren presets, pointing out the independently estimated angle.
3. Show injected direction dropout and explain the general warning.
4. Show competing sources and explain that reliability checks can still fail.
5. Run the quick experiment and compare errors, misses and delay together.
6. Download a CSV or open a saved graph to show reproducible evidence.

Save a short screen recording before the presentation as a backup. Keep your source code, exported results and this guide together.

## 13 Know the remaining scope

The completed software prototype includes signal generation, the existing array model and GCC-PHAT processing, DEDA and baseline execution, visual motors, replay, logs, experiments and exports. It makes a defensible simulation project.

It does not include a trained MFCC/CNN classifier, genuine recorded multichannel audio, a validated room/body model, embedded deployment, physical battery/motor measurements or user evaluation. The shout is modulated noise, not a real human recording. The reflection condition adds a single delayed plane wave, not a full room impulse-response model. Timing faults and direction dropouts are explicit fault injections. The source is far-field and synthetic fractional delays are circular; do not infer wearable performance or distance accuracy from it.

To extend the project later, add recorded source clips, a trained classifier with source-separated train/test data, a room-acoustic simulator, and then hardware. The present prototype is complete for the stated acoustic and decision-policy simulation scope.

## Troubleshooting

| Problem | Action |
| --- | --- |
| `ModuleNotFoundError: numpy` | Install `requirements.txt` using the same Python executable that starts the server |
| Port 8765 is in use | Reuse the existing server, or run `python python\simulator_server.py --port 8766` and open the matching address |
| Browser says disconnected | Start the Python server; use its HTTP address rather than opening the HTML file |
| No alert at low confidence | Inspect the evidence log; rejection can be the correct output |
| A beep gives all four motors | Its direction may be ambiguous; check the measured reliability values |
| Noise slider does not change class confidence | Expected: the classifier is a separate scripted input, not an audio recognition model |
| Different angle during the ambient tail | Noise has no true source direction; scrub to a window while the source is active |
| The experiments do not match the paper | They are different experiments; use `run_synthetic.py` for the original decision-stream benchmark |
| Share a public URL | This version is local; Python must be running on the demonstration computer |
