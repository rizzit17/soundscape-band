# Wiring

Fill in the GPIO numbers you actually used. The constraints below are what matters for the algorithm to work.

## Microphones (I²S) — must be sample-synchronous

An INMP441 shares a data line with at most one other mic (L/R select), so 3 mics need **two data lines driven by the same BCLK and WS**. If the third mic runs on its own clock, every TDOA involving it is wrong (the plane-wave norm check in DEDA will flag it, but the direction is lost).

| Signal | Mic 0 (front) | Mic 1 | Mic 2 | MCU GPIO |
|---|---|---|---|---|
| VDD | 3.3 V | 3.3 V | 3.3 V | — |
| GND | GND | GND | GND | — |
| SCK (BCLK) | shared | shared | shared | |
| WS (LRCLK) | shared | shared | shared | |
| SD (data) | line A | line A | line B | A: ___ B: ___ |
| L/R | GND (left) | VDD (right) | GND (left) | — |

- **RP2040:** one PIO program generating BCLK/WS and sampling two consecutive data pins (A, B) on the same clock edge.
- **ESP32:** I2S0 as master (BCLK/WS) on line A; I2S1 as slave sharing the same BCLK/WS on line B. Verify sync by recording a click and checking closure ≈ 0 in `acoustic_checks`-style analysis.

## Motors

| Motor | Position | Bitmask | MCU GPIO (PWM) | Driver |
|---|---|---|---|---|
| M0 | Front (0°) | 1 | | MOSFET/transistor + flyback diode |
| M1 | Right (90°) | 2 | | ″ |
| M2 | Back (180°) | 4 | | ″ |
| M3 | Left (270°) | 8 | | ″ |

## Power

Li-ion 3.7 V → TP4056 (charge + protection) → switch → 3.3 V regulator on the MCU board. Motors from the battery rail through their drivers; add a bulk capacitor near the motors to avoid brown-outs during vibration.

## Schematic

Add `schematic.pdf` (KiCad/EasyEDA export) and photos in `photos/`.
