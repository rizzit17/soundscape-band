# Browser listening demo

Run `Start-Simulator.cmd` from the repository root, or `python python/simulator_server.py`, then open http://127.0.0.1:8765. Restart an already-running Python server after updating, and refresh the browser.

## Review walkthrough

1. Click **Hear & watch this scene**. It enables browser audio with your click, starts at model time zero, and scrolls to the wearer and explanation.
2. Follow the horn sound, direction estimate and Back command. The animated motor highlights represent commands, not physical vibration.
3. Click **Next demo case** for siren-left, direction dropout, uncertain class and ambient control. Each case is recomputed by Python on selection; existing results can be replayed directly.
4. In the dropout scene, look for **Class accepted; gathering direction evidence**, then the general four-output warning. The missing observation is deliberately injected; audible sound does not guarantee usable direction data.
5. Use **Play / pause**, **Sound on/off**, the timeline, individual window buttons and replay speed. Volume is in the listening panel. Sound starts muted, at 20% when enabled. Available speeds are 0.25×, 0.5×, 1× and 2×. Replay speed changes both signal duration and pitch; use 1× for normal listening.
6. For a deeper review, inspect the three waveform plots, geometry checks, baseline comparison, and window trace. Existing experiment and review-checklist tabs are preserved.

## What you hear

The engine returns 16 kHz, mono, signed 16-bit PCM samples from the same synthetic microphone-1 channel passed to GCC-PHAT. This includes the configured noise, competing source or reflected copy. A single clip-wide gain limits the peak to 85% before the browser volume control. It preserves relative event/noise amplitude but is not calibrated sound pressure or comparable loudness across clips. It is not spatial audio, a microphone recording, or a trained recognizer. The shout example is speech-like noise, not intelligible speech.

DEDA's class input remains scripted and independent of the audio SNR. Sound playback makes the scene understandable; it does not add real sound recognition. Source ripple animations indicate the event's active interval; motor highlights reflect actual policy alerts and stay selected for inspection. Their pulses are illustrative. A no-alert scene can represent a miss, not proof that withholding an alert was correct. Per-window geometry checks can pass on a wrong direction.

The audio clock drives replay time while audio is enabled. Pausing, seeking, selecting another scene, switching tabs or hiding the page stops the current audio source. Playback restarts from the selected model timestamp. If browser audio is unavailable, the visual replay remains usable. Model delays remain simulation results, not measured hardware timing.

## Verification

`python -m pytest python/tests/test_simulator.py -q -p no:cacheprovider` (set PYTHONPATH=python) checks the simulation and HTTP service. The audio regression checks decoded samples against every plotted mic-1 window within 16-bit quantization tolerance. `node simulator/app.test.cjs` checks replay projections and outcome interpretation.

## Presentation and key moments

Use **Presentation mode** in the top bar for a focused review view. It keeps the virtual wearer, the live explanation, policy comparison and playback controls visible while hiding settings and tables. **Exit presentation** restores the complete lab. The mode is a page layout, not browser fullscreen.

The Baseline B / DEDA comparison shows the latest actual command from each policy at the selected model time. It does not assume DEDA is always better: the horn case explicitly shows its extra decision delay. Jump buttons use the computed alert timestamps; a warning jump is disabled when that policy emits no alert. **Sound begins** jumps to the configured source onset, before the first complete event window in the default scene.

The full lab's class-evidence panel shows the policy's four post-step accumulated scores. Scores can reset to zero in the same step that emits an alert. Bars clip to the range -8 to +8 for display, while numerical labels retain the score. These values are neither probabilities nor a measured classifier output.


## Run scene and alternate port

**Run scene** recomputes the current settings and immediately starts replay from model time zero, even when the settings have not changed. It preserves the mute setting. **Listen & replay** enables audio and can reuse the matching computed scene. On initial page load, the automatic computation is paused for inspection.

For the review-session port, use `python python/simulator_server.py --port 8766`, then open http://127.0.0.1:8766. The default remains 8765. The server must keep running on the same computer; no public deployment is configured.

Latest submission: [Word report](../docs/submission/SoundScape_Final_Report_Updated.docx) and [Word paper](../docs/submission/SoundScape_Final_Research_Paper_Updated.docx).
