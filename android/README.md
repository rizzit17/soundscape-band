# SoundScape Lab — Android prototype

An offline, foreground-only microphone testing companion for the SoundScape Band simulation. It runs Google's pretrained YAMNet model through MediaPipe Audio Classifier. It is not a hardware implementation of the band and is not a safety alarm.

## Install and test

1. Copy `SoundScape-Lab.apk` to your Android phone using USB, Drive, or another file-transfer method.
2. Open the APK in Files. If Android prompts you, allow that file app to install this APK. You can turn that permission off afterward.
3. Open **SoundScape Lab** and tap **Start listening**. Allow microphone access while using the app.
4. For exploration, leave the expected label as **Unlabelled exploration**. For evaluation, select the sound you intend to play before starting a session.
5. Play a sound from a separate laptop or speaker at a comfortable level. Keep the app open. It stops using the microphone when you leave it or lock the phone.
6. Stop listening, change the expected class, and repeat. Export the CSV after testing. The log is stored privately on the phone until you export it; no audio is saved or uploaded.

The APK is debug-signed for direct installation, not a Play Store release. Minimum Android version is 8.0; ARM64 is the intended phone architecture. Actual phone compatibility and audio performance must be checked on the Motorola Edge 40.

## Vibration update 0.2

Install version 0.2 over the previous app to retain private test logs. Tap **Test vibration (no sound needed)** before listening. This explicitly requests a long pulse even if the automatic Vibration alerts switch is off. If you feel nothing, use **Open phone sound settings** to check vibration intensity and Do Not Disturb. Android can filter a successful vibration request; the app cannot confirm physical motor movement.

Automatic alerts now default to one qualifying target window. Turn on **Require two matching windows** before starting if you prefer the previous persistence rule. Both modes use a three-second shared cooldown. The alert status explains whether the app is waiting for a target score, confirming a second window, cooling down, or triggering an alert. Labels outside the four mapped groups can appear in the model results without causing vibration.

Pulses use explicit maximum amplitude where supported and notification vibration attributes. Phone sound settings still apply. The CSV `alert` field records a policy trigger, not evidence that a motor physically vibrated. New `config` rows record app version, required windows and cooldown; ignore these rows when counting audio windows. Record version and mode when comparing new trials with version 0.1.

## What it does

- Captures 16 kHz mono PCM in 15,600-sample (975 ms) windows.
- Displays the five highest model labels and the highest score among four mapped target groups.
- Uses the maximum score in each group, not a sum or a softmax normalization. Model scores are not calibrated probabilities.
- Requires one qualifying target window by default, or two consecutive windows of the same group when confirmation is enabled. All alerts share a 3-second cooldown. The default threshold is 0.30 and is adjustable before a session.
- Generates distinct general phone vibration patterns: horn = two pulses; siren = long pulse; reversing = three short pulses; shouting = short–long.
- Logs each classified window, expected label, target score, threshold, alert flag, inference duration, relative input level in dBFS, and optional manual feedback.

This phone persistence gate is separate from the repository's DEDA algorithm. It does not infer source direction, implement four independent wearable motors, or validate the paper's 300 ms target. Recorded inference time excludes audio capture, buffer delay, UI scheduling, and actuator delay; it is **not end-to-end alert latency**. dBFS is a relative digital signal level, not a calibrated sound-pressure measurement.

## Class mapping

| App group | YAMNet class indices |
|---|---|
| Horn | 302 vehicle horn; 303 toot; 312 air/truck horn; 325 train horn |
| Siren | 317 police siren; 318 ambulance siren; 319 fire-engine siren; 390 siren; 391 civil-defense siren |
| Reversing beeps | 313 reversing beeps |
| Shouting | 6 shout; 7 bellow; 8 whoop; 9 yell; 10 children shouting; 11 screaming |

`Other / uncertain` means no mapped target cleared the threshold. It does not establish that the environment is safe or silent. Generic beeps, speech, and smoke alarms are not automatically mapped into these four groups.

## Evaluation for the project report

Use at least 10 distinct recordings per target class and 10 negative/background examples. Prefer unseen clips from different sources; avoid repeating one clip as if it were many independent examples. Start playback before tapping Start for approximately steady-state window comparisons, then keep playback going until Stop. Use a separate protocol if measuring sound-onset latency.

Run each example for 10–15 seconds at fixed distance and volume. Record clip identity, expected class, distance, volume setting, environment, and phone model in a separate trial sheet. Repeat a subset with background noise. Keep a development set for choosing the threshold and a separate held-out set for final results; report the chosen threshold.

For each trial, count whether the expected alert occurred, whether any incorrect alert occurred, and how many alert repetitions occurred. Include misses and false alerts. Report window-level confusion separately from event/trial-level detection. The app's expected-class match count is a **window-level** convenience statistic and is not a complete accuracy estimate. Feedback rows reference the original window's `id_utc_ms` and session; they are annotations, not additional observations.

Exported columns: `kind,session,id_utc_ms,session_elapsed_ms,expected,detected,target_score,threshold,alert,inference_ms,input_dbfs,feedback`. Logs persist across sessions and app restarts. Clearing app data or uninstalling removes private logs, so export first.

Keep two distinct report sections: (1) virtual microphone-array/DEDA simulation; (2) real-audio smartphone recognition and haptic prototype. Do not substitute phone results for the simulated wearable's direction or timing claims.

## Build

Install JDK 17 and Android SDK platform 36. Set `ANDROID_HOME` or write an ignored `local.properties` containing `sdk.dir=...`. Run `Build-Android.ps1` from PowerShell. It downloads the public model if missing, checks its SHA-256, and invokes the Gradle wrapper. Internet is needed for the first build, but the app itself works offline.

Unit tests: `./gradlew.bat testDebugUnitTest`.
Android model integration test (device/emulator attached): `./gradlew.bat connectedDebugAndroidTest`.
Static checks: `./gradlew.bat lintDebug`.

## Model provenance

- Model: Google YAMNet float32, 521 AudioSet classes; no project-specific training or fine-tuning.
- Download: https://storage.googleapis.com/mediapipe-models/audio_classifier/yamnet/float32/latest/yamnet.tflite
- Retrieved: 2026-10-24.
- SHA-256: `4d8b4a53282dc83ef04e3e7dbc4fbc98082e34e44ed798e16c3a0cdd4c584faf`.
- Runtime: `com.google.mediapipe:tasks-audio:1.1.1` (pinned).
- Model documentation: https://github.com/tensorflow/models/tree/master/research/audioset/yamnet
- Android API documentation: https://ai.google.dev/edge/mediapipe/solutions/audio/audio_classifier/android
- Upstream projects use Apache License 2.0; retain upstream licensing when redistributing. Their model accuracy does not establish the accuracy of these grouped labels in this application.
