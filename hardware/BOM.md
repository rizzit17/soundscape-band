# Bill of materials

Target total: **≈ ₹1,650** (Review-2 estimate). Fill in the actual supplier prices you paid.

| # | Component | Qty | Specification | Purpose | Unit price (₹) | Total (₹) | Supplier / link |
|---|---|---|---|---|---|---|---|
| 1 | Microcontroller | 1 | RP2040 board (preferred) or ESP32 | DOA, classification, DEDA | | | |
| 2 | MEMS microphone | 3 | INMP441, I²S, 24-bit | Microphone array (≈35 mm triangle) | | | |
| 3 | Coin vibration motor | 4 | 3 V ERM coin motor | Front / right / back / left haptics | | | |
| 4 | Motor driver | 4 | Logic-level N-MOSFET or NPN transistor + flyback diode + gate/base resistor | Drive each motor from a GPIO/PWM pin | | | |
| 5 | Battery | 1 | 3.7 V Li-ion, 500 mAh | Power | | | |
| 6 | Charger | 1 | TP4056 module (with protection) | Charging | | | |
| 7 | Enclosure | 1 | Soft fabric neckband / armband + 3D-printed mounts | Wearable housing | | | |
| 8 | Misc. | — | Wires, perfboard/PCB, connectors, switch | Assembly | | | |
| | | | | | **Total** | | |

## Notes

- Mount the three microphones as an equilateral triangle and **measure the actual positions** on the finished band; put them in `python/deda/doa.py` (`triangle_positions`) and regenerate the matrix P for the C code.
- Motors at 0° (front), 90° (right), 180° (back), 270° (left), matching the test layout and the code's motor bitmask (F=1, R=2, B=4, L=8).
