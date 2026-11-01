# Real-audio ML lab

The normal homepage now uses the trained model directly in its wearer simulation. [Main-view walkthrough](MAIN_MODEL_SIMULATION.md). Open `/ml` for training, evaluation and diagnostics.

## What is implemented

- Complete ESC-50 preparation, supervised training, validation and held-out testing.
- 50-class log-mel + logistic-regression baseline trained from scratch on the actual WAVs. This is not YAMNet, a deep model, or a claimed state-of-the-art classifier.
- Fixed source-aware split: predefined folds 1-3 train (1,200 clips), 4 validate (398 after source exclusions), 5 test (400). Two fold-4 clips sharing original sources with fold 5 are excluded from validation. Sources crossing folds 2/3 remain within training. Original test fold 5 stays intact. This is **one holdout**, not five-fold cross-validation.
- Features and scaling fitted without test data. A temperature is selected on validation only. No random window split or energy-selected test crop.
- Evaluation JSON with accuracy, macro F1, per-class precision/recall/F1, a confusion matrix and source-group bootstrap accuracy interval. Test predictions, split manifests and file checksums are exported.
- NumPy-only model export, with a parity assertion against training predictions. Serving never unpickles a model.
- Untouched test examples and PCM WAV uploads with actual waveform-derived predictions. Ground truth is shown separately and never used as a prediction input.
- The reference Python DEDA now accepts explicit class indices and threshold arrays. The original four-class default and C/Wokwi implementation are unchanged. This is not the old single-Horn-slot demonstration trick.

## Train and test on this computer

From the repository root:

```powershell
python -m pip install -r requirements-ml.txt
$env:PYTHONPATH = 'python'
python -m soundscape_ml.train prepare
python -m soundscape_ml.train train
python -m soundscape_ml.evaluate
python python/simulator_server.py --port 8766
```

Open `http://127.0.0.1:8766/ml`. The local page can also start preparation/training as background jobs and display progress. It refuses a second ML job while one is running. Training needs the dataset locally and the packages in `requirements-ml.txt`; normal model inference needs only NumPy.

The downloader obtains the public ESC-50 ZIP (~600 MB). Raw recordings, the archive and feature cache live under ignored `data/raw/esc50/`. Do not commit the full dataset. Models are under `models/esc50/`; measured reports and source/split manifests under `results/esc50/`. `model.npz` and reports must have matching checksums before the UI declares the bundle ready.

The training command evaluates the untouched test split after fitting and validation. Do not choose new parameters after seeing test results and continue calling the same split untouched. For research claims, predeclare a five-fold protocol or collect a genuinely new final test set. These results are separate from the earlier paper's synthetic decision-stream study.

## Warning behaviour

Configured named warning classes are dog, car horn, siren, glass breaking, clock alarm, knocking and crying baby. Rain supplies an information cue, not a danger designation. Other recognized dataset labels remain visible without an automatic warning. Low confidence can withhold a cue. The closed-set classifier can still confidently misclassify an unfamiliar sound; no validated open-set detector is claimed.

DEDA receives the full 50-category probability vector and uses the actual dataset indices for configured events. Its new ML operating point uses a 256 ms hop, class thresholds 2.0/1.6/3.0 for initial/floor/urgency, 0.35 opening, and the existing 0.5 evidence margin. The 300 ms episode target yields K=0 at this hop; this mode is not a demonstration of multi-window waiting at 64 ms. Thresholds are illustrative, not a safety-calibrated user operating point. A fixed 0.70 class-only baseline is included in prediction exports.

A mono dataset recording has **no real directional ground truth**. By default this lab passes missing direction to DEDA and emits general four-output commands. An optional virtual-array setting propagates the recording through the existing ideal 35 mm triangle at a chosen angle/SNR, recognizes the simulated Mic 1 audio and computes GCC-PHAT direction observations. Those directions are explicitly synthetic, and those noisy/altered scenes are outside the clean dataset accuracy. Do not call them localized real-world results. The separate scene explorer retains its virtual three-microphone geometry.

## Timing and evaluation boundaries

Recognition requires 16,384 samples (1,024 ms) before its first prediction. It then produces a fresh prediction every 4,096 samples (256 ms). A future prediction is never reused to make an earlier warning. The final clip label is an offline average of window probabilities; it is not the first-event detection result.

Do not claim this pipeline meets a 300 ms onset deadline: its input context alone exceeds that. ESC-50 clip labels do not supply exact event onsets/offsets, so the lab does not invent onset-to-warning latency, missed-event rates or false alerts per ambient hour from them. Displayed warning timestamps are relative to **clip start**. Server computation time is separate from required audio context and does not establish physical MCU timing.

Clip-level accuracy, macro F1 and per-class errors must be read separately from DEDA warning acceptance. A correct classifier label may be too uncertain for a warning; a wrong prediction may trigger one. Uploaded recordings are outside the measured test set and have no verified truth label.

## Hosted version

`deployment/prepare_vercel.py` bundles the compact model, card, measured evaluation and selected held-out examples. Hosting supports status, test-example predictions and bounded WAV upload predictions. Training endpoints are deliberately absent on Vercel: do training locally, then prepare and deploy the updated bundle. Source audio is not stored by the application on upload; deployment-provider request processing remains subject to that provider's policies.

## Licensing and provenance

ESC-50 by Karol J. Piczak: https://github.com/karolpiczak/ESC-50

Dataset terms: CC BY-NC 3.0 (ESC-10 subset CC BY 3.0). Original clips have per-creator terms. The full upstream attribution listing is preserved as `models/esc50/ESC50_LICENSE.txt`; `examples.json` maps each bundled WAV to its source and processing. Audio/data assets are not covered by the repository code license. Use this model/demo for noncommercial educational evaluation; check upstream terms before other uses.

No model result proves wearable safety, physical vibration effectiveness, battery performance or benefit to Deaf/hard-of-hearing users. No existing report/paper numerical claim is silently replaced.

Prediction exports include the input/model checksums, class list, full per-window probability vectors, policy configuration, direction observations (only for the optional virtual array), and actual commands. They distinguish clip-average classification from individual causal warning decisions.

## Measured baseline result

The completed run achieved 42.75% clip accuracy and 40.68% macro F1 on 400 test clips. Accuracy 95% source-group bootstrap interval: 37.29%-48.46%. This is limited baseline performance, not evidence that sound recognition is solved. [Full measured results and mistakes](../results/esc50/README.md). For exact reproduction use Python 3.13.7 and `requirements-ml-lock.txt`; the general requirements file supports installing a compatible training environment but does not promise identical results across versions.
