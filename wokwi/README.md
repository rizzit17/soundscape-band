# SoundScape Wokwi demonstration

This is a supplementary virtual ESP32 demonstration of the DEDA decision policy. Use the existing Python/web simulation as the main acoustic demonstration.

## What it does

Prepared synthetic class probabilities and direction observations are passed, window by window, into the project's actual C DEDA implementation. An OLED explains the decision, five buttons select scenarios, and four pulsing LEDs illustrate the motor command that the policy emits. The firmware calculates the decision; it does not simply select an expected LED for each case.

It does not listen through your laptop microphone, recognize real sounds, run GCC-PHAT on the ESP32, model a vibration motor, or demonstrate a working wearable. Wokwi LEDs represent output commands.

## Set up online

1. Extract the ZIP to a folder on your computer.
2. Open https://wokwi.com/projects/new/esp32 in your browser. Sign in if you want to save a project link.
3. Select the **Code** tab if the editor is hidden.
4. Open `sketch.ino` in the extracted `sketch` folder with a text editor. Copy all its text, select all text in Wokwi's `sketch.ino`, and paste to replace it.
5. Replace Wokwi's `diagram.json` with the complete contents of the supplied `sketch/diagram.json` in the same way. The board, LEDs, resistors and wiring are already described there; you do not have to draw them manually.
6. Use the file menu (the small arrow next to the editor file tabs), then **New file...**, to create three additional files: `deda.h`, `deda.c` and `scenario_data.h`. Copy the full contents of each matching supplied file. Keep the names exactly the same, including extensions. Also create `libraries.txt` and copy the supplied contents. You should now have six project files: `sketch.ino`, `diagram.json`, `deda.h`, `deda.c`, `scenario_data.h`, `libraries.txt`.
7. The supplied `libraries.txt` requests Adafruit SSD1306, Adafruit GFX Library and Adafruit BusIO; Wokwi installs these for its build. Select **Simulation**, then press the green **Start the simulation** button. Allow the first build to complete.
8. The first case starts automatically. The Serial Monitor explains the controls and displays the decisions.
9. Click a labelled scenario button on the diagram. Alternatively, in the Serial Monitor input, type a case number from `1` to `5` and press Enter. Use the table below to check the output. If the input is hidden, expand the Serial Monitor panel.
10. Save the project while signed in, give it a name such as **SoundScape DEDA Decision Demo**, and copy the resulting project URL for your presentation.

The ZIP is a file bundle; do not paste the ZIP itself into the editor. The `expected_results.json`, generator and host test are reproducibility helpers and do not need to be added to Wokwi.

## Demonstration cases

| Send | Input case | Expected output | Model onset-to-command delay |
|---|---|---|---|
| 1 | Horn behind | Back LED, directional warning | 128 ms |
| 2 | Siren on the left | Left LED, directional warning | 64 ms |
| 3 | Accepted horn, direction observations removed | All four LEDs, general warning | 192 ms |
| 4 | Low class confidence (0.30) | No alert, LEDs off | No alert |
| 5 | Ambient only | No alert, LEDs off | No alert |

`r` repeats the selected case, `c` stops and clears the LEDs, and `h` prints help. Starting a case clears the previous state and LEDs. The last decision remains on the OLED. Directional outputs repeat a single 260 ms light pulse every 1.2 seconds; general warnings repeat two 140 ms pulses on all four outputs. These are illustrative animations, not new policy alerts or validated haptic encodings. Each case takes several seconds.

The internal model uses 64 ms analysis steps. The display deliberately plays each step every 650 ms. Printed delay is the alert's model timestamp minus the prepared source onset (192 ms), not elapsed wall time or measured sound-to-vibration latency. The default policy also reserves a modeled processing allowance; this allowance is not a measurement.

The LED mask uses Front=1, Right=2, Back=4, Left=8. A mask of 15 means all four. GPIO pins are Front=18, Right=19, Back=21, Left=4, through 330-ohm resistors.

## Explain it during the review

Say: "Our submission is a simulation study. The web simulation demonstrates synthetic acoustic processing and the decision trade-offs. This additional Wokwi demonstration runs the same C decision policy on a virtual ESP32 using prepared observations. The LEDs show the motor commands. In case three, the system accepts a sound event but cannot trust a direction, so it issues a general warning."

Do not say that the system detects sound through Wokwi microphones, that the LEDs prove vibration effectiveness, or that virtual execution proves real hardware latency, energy use or full-pipeline feasibility. Passing geometry checks does not guarantee a correct direction; the larger study addresses incorrect-but-plausible estimates.

These are five teaching cases, not an expanded evaluation dataset or a substitute for the report's held-out benchmark. They use the web demonstration's default thresholds, which differ from the separately documented research-study operating point. The class probabilities are scripted, not classifier predictions from real recordings.

## Troubleshooting

- `deda.h: No such file`: add `deda.h` as a separate file, with that exact name.
- `undefined reference to deda_step`: make sure `deda.c` is present, not renamed `.txt`, and retain the `extern "C"` wrapper in the supplied sketch.
- No response to a number: type into the Serial Monitor input, not the code editor, then press Enter.
- All LEDs stay off: case 4 and case 5 intentionally produce no alert. Try `1` and wait for the alert line.
- LEDs show the previous case: select a new number or send `c`. Each new case clears the output.
- Simulation build requires an online service: keep the existing web simulation ready as the main demo. Local ESP32 compilation does not guarantee online service availability.

## Reproduce the prepared inputs

From the repository root, with the project's NumPy dependency installed:

```powershell
python wokwi/generate_scenarios.py
```

This regenerates `scenario_data.h`, `diagram.json` and `expected_results.json` from `python/deda/simulator.py`. The bundled `deda.c` and `deda.h` are unchanged copies of `c/deda.c` and `c/deda.h` at preparation time. `build_diagram.py` generates the upgraded layout and must accompany the generator in the repository. The adapter processes all windows through `deda_step`. `verify_host.c` replays those exact arrays on the host.

Official references: https://docs.wokwi.com/guides/esp32 and https://docs.wokwi.com/diagram-format.


## Upgrading an existing Wokwi project

Stop the simulation. Replace BOTH `sketch.ino` and `diagram.json` with the new versions. Add `libraries.txt`. Keep the existing three C/data files, or replace them with the matching supplied copies. Restart. The left LED moved from GPIO22 to GPIO4 because the OLED uses GPIO22 for its clock. Mixing the old diagram with the new sketch will not work correctly.

OLED I2C uses SDA=23, SCL=22. Buttons use INPUT_PULLUP on GPIO13,14,25,26,27, with their other contact wired to ground. Software debouncing is 35 ms. Scenario changes reset the decision and pulse state. GPIO timing, display rendering and the slowed replay are presentation behaviour outside the unchanged C DEDA policy.

The OLED shows the selected scenario name (ground-truth input label), the actual policy stage and output. A selected scenario title is not a classifier prediction. `CLASS ACCEPTED / Waiting direction` comes from DEDA's latched class state; final decisions come only from emitted alerts.

No buzzer is included: this demonstration communicates through the display and simulated haptic outputs. No live microphone processing has been added.

## Validation performed

The five prepared cases were replayed through compiled C on the host; alert count, timestamp, kind, class and motor mask matched Python. The core C/header copies remain byte-identical. The upgraded firmware is checked with the Arduino ESP32 toolchain. Online circuit execution must still be verified after uploading the six project files; compilation alone is not a virtual LED or OLED test.

The upgraded sketch compiled successfully for ESP32 using Arduino ESP32 core 3.3.7, Adafruit SSD1306 2.5.17, GFX 1.13.0 and BusIO 1.17.4. Compiler report: 343,612 bytes program storage; 24,052 bytes global variables. These figures describe the replay/display sketch only, not the complete audio pipeline or peak runtime memory.
