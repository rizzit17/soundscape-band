# Main simulation: real recording mode

Open the normal simulation homepage. When a trained model is available, the default input mode is **Real recording + trained model**.

1. Choose a held-out recording, upload a PCM WAV, or press **Random recording & direction**.
2. Set the virtual source angle. This defines where the simulated source is placed, not the estimated answer.
3. Press **Run scene** or **Hear & watch**. The actual recording is propagated to three virtual microphones. The recognizer uses virtual Mic 1; GCC-PHAT computes pairwise delays and direction from the three channels.
4. Watch the same wearer, estimated-angle arrow, reliability checks, class trace, evidence and DEDA motor commands. Class scores are model outputs; the manual class-score control is hidden.
5. Try a different angle, lower SNR or direction dropout. Classification, localization and warnings are recomputed. Failures, wrong predictions and no-warning outcomes are retained.

The replay has 256 ms steps and needs 1,024 ms of audio before its first prediction. First-warning times are measured from **clip start**, not an annotated sound onset. No claim of a 300 ms onset deadline is made.

80 dB is the default added-noise setting: almost no additional synthetic noise. The original recording can already contain background noise. Lowering this can greatly degrade the compact baseline, which achieved only 42.75% accuracy on the separate clean 400-clip test fold. Do not claim that the altered virtual scenes reproduce that benchmark or that every example works.

The whole-clip prediction is an offline average. Live replay explanations use only predictions available at the selected clip time. No class or warning is shown before the first analysis context is complete. Ground-truth recording labels are used for comparison after inference, not supplied to the recognizer.

Directions are **computed but simulated**: these public examples are mono recordings, not synchronized three-microphone wearable captures. The virtual array supplies spatial observations. Real recorded localization validation would need multichannel recordings with source direction annotations.

The main scene exports all 50 probabilities per step, actual direction observations, evidence, alerts, input/model hashes and audio. CSV column names are the dataset categories, not the old five supplied-score classes. Uploaded filenames are not recognition inputs.

The original scripted cases are still available under **Scripted teaching cases**. Those cases and the 26-case Review checklist illustrate policy behaviour and are not model accuracy tests. The ML lab at `/ml` is retained for training, evaluation and detailed diagnostics; it is no longer necessary to leave the main page to see model-driven motors.
