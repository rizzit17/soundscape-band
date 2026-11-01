# SoundScape: Short Project Study Guide

## 1. What is our project?

SoundScape studies how a sound-warning band could decide **when to warn and whether to show a direction**.

Our current submission is a **simulation**, not a completed physical band. Lights and on-screen motors represent possible vibration commands.

**Say this to sir:**

> We built a simulation that separates recognizing an important sound from trusting its direction. If the sound is accepted but the direction is uncertain, it can give a general warning instead of pointing somewhere unreliable.

## 2. What is DEDA?

**DEDA means Dual-Evidence Deadline Alerting.** It asks two separate questions:

1. Is there enough evidence for an important sound?
2. Is there enough evidence to trust its direction?

| Situation | Decision |
| --- | --- |
| Sound accepted and direction trusted | Show the direction. |
| Sound accepted but direction uncertain | Wait briefly; give a general warning if direction remains uncertain. |
| Not enough sound evidence | Keep checking within a limited period, or reject the event. |

**One directional light** means Front, Right, Back or Left. **All four** mean a general warning with no direction claimed. Near a direction boundary, two neighbouring lights can represent the direction.

The **300 ms setting is a model target**, not a guaranteed real-device response time.

## 3. How does the browser simulation work?

[Open the browser simulation](https://soundscape-simulation.vercel.app/)

```text
Generate sound -> simulate three microphones -> calculate direction
                                               |
Supply sound-class scores --------------------> DEDA -> warning command
```

- Three virtual microphones receive slightly different versions of the generated sound.
- **TDOA** means the difference in sound arrival time between microphones.
- **GCC-PHAT** estimates that difference so we can calculate a direction.
- Reliability checks ask whether the direction evidence looks consistent.
- DEDA decides how to warn using sound evidence and direction evidence separately.

**Important:** The sound and direction are calculated, but sound-class scores are supplied by the simulation. The browser does not use a trained sound recognizer. The sound you hear is generated, not a real recording.

### What to show

1. **Horn behind:** play the sound and show the Back command.
2. **Direction dropout:** show that an accepted sound can produce a general warning.
3. **Uncertain class:** show that low sound evidence can produce no alert.
4. Use **0.25x** to explain decisions slowly; use **1x** for normal listening. Slowing replay also changes audio pitch.

The browser has **12 sound examples**. Dog, glass, rain and emergency siren now use credited recorded sources placed into a virtual microphone array. The remaining sounds are generated. Every added sound has its own named demo warning; rain gives a general information cue. The labels/scores are supplied, not recognized. Added sounds reuse a policy evidence lane and do not expand the paper's four-class benchmark.

In **Review checklist**, run the original five cases plus three checks for each added sound: accepted input, missing direction and low confidence. Each warning also has a distinct illustrative pulse sequence; these patterns have not been user-tested.

## 4. What do the two Wokwi demos show?

### Wokwi 1: actual C policy with prepared inputs

[Open Wokwi 1](https://wokwi.com/projects/479065380305937409)

The buttons choose prepared inputs. The actual C DEDA policy decides the output; the buttons do not directly select an LED answer.

| Case | Expected command |
| --- | --- |
| Horn behind | Back light |
| Siren left | Left light |
| Missing direction | All four lights: general warning |
| Uncertain class | No warning |
| Ambient | No warning |

**Say:** "This shows the decision stage on a virtual ESP32. It does not process live microphone audio."

### Wokwi 2: interactive explanation with knobs and switches

[Open Wokwi 2](https://wokwi.com/projects/479067404737540097)

- **Knobs:** change source angle, supplied sound score and noise setting.
- **SOUND switch:** starts a scene. Turn it OFF before changing settings, then ON again.
- **DROPOUT:** removes usable direction evidence.
- **COMPETE:** creates a believable but wrong direction, opposite the target.
- **Green lights:** simplified DEDA commands.
- **Red lights:** this sketch's simpler baseline commands.
- **Yellow WAIT:** collecting evidence.

Show a normal case, then dropout, then COMPETE. Use a high sound score, around 0.90, for accepted-sound examples.

**Say:** "This is a simplified teaching model. COMPETE shows that even consistent-looking direction evidence can be wrong."

The two Wokwi demos use different implementations. Wokwi 2 does not run the full reference DEDA policy or GCC-PHAT on audio. Its baseline can use a garbage angle during dropout, while the browser baseline can give a general warning. Do not compare their few scenes as identical experiments.

## 5. How do I explain the Serial Monitor?

| Output | Simple meaning |
| --- | --- |
| Reset/boot messages | The virtual board is starting. |
| Class score/evidence | Support for an important sound. Accumulated evidence is not a percentage. |
| Estimated angle | Calculated source direction. |
| Gates PASS/FAIL | Whether the direction passes consistency checks. PASS does not guarantee correctness. |
| DIRECTIONAL | Sound accepted and direction trusted. |
| GENERAL | Sound accepted; no direction claimed. |
| No alert/rejected | The policy did not accept a warning. |

**Masks:** Front=1, Right=2, Back=4, Left=8; all four=15.

Printed delays are **model times**, not measured sound-to-vibration times. For example, Wokwi 1's horn starts at 192 model ms and warns at 320 ms: the delay is **128 ms**. Its display is deliberately slowed for explanation.

## 6. What does the research paper prove?

The main test uses **100 generated streams containing 3,594 events**. A separate direction-estimation study uses **4,200 synthetic scenes**. These are not real wearable recordings.

| Main result | Baseline B | DEDA |
| --- | --- | --- |
| Wrong-direction events | 20.31% | 2.45% |
| Missed-or-late events | 10.19% | 15.32% |

**Explain the trade-off:**

> DEDA reduced misleading direction commands in our synthetic study, but more warnings were late. It is not better on every measure.

The wrong-direction percentage uses all critical events as its denominator. It is not overall system accuracy. DEDA also produced **286.8 false alerts per simulated ambient hour**, so the results do not establish acceptable real-world performance.

The live demos explain individual decisions. They do not reproduce these study percentages. Simple immediate-fallback and no-direction-wait policies remain strong alternatives.

The paper describes the browser and Wokwi 1. Hosting, the extra sound examples and Wokwi 2 are later demonstration additions; they do not change the paper's numerical results.

## 7. Main viva answers

**What is your contribution?**
DEDA's warning decision: separate sound acceptance from direction acceptance, limit waiting, and allow a general warning. GCC-PHAT, TDOA and geometric checks are existing methods.

**Why give a general warning?**
To retain an accepted sound warning without claiming an uncertain direction.

**Can a wrong direction pass the checks?**
Yes. A competing source can produce a believable wrong estimate. We demonstrate this limitation.

**Why no light even when sound plays?**
Hearing the generated sound does not mean its supplied class score was accepted. No alert can also be a missed event.

**Have you tested a real wearable or vibration?**
No. We show synthetic processing and virtual output commands. Physical vibration, battery use and full-board processing time remain unmeasured.

**Is DEDA always faster or better?**
No. Waiting can increase delay, and simpler fallback approaches can be preferable. We report the trade-offs.

**What comes next?**
Test synchronized real recordings, evaluate the full pipeline on hardware, measure actual motor activation and evaluate cues with users under ethical approval.

## 8. Your presentation order

1. Explain the problem and DEDA in one minute.
2. Browser: Horn behind, Direction dropout, Uncertain class.
3. Wokwi 1: directional command versus general warning.
4. Wokwi 2: normal, dropout and plausible wrong-direction case.
5. Show the two paper result rows and explain both benefits and costs.

**Closing line:**

> Our contribution is a repeatable simulation of warning decisions and their trade-offs. We have not yet established real wearable performance or user benefit.

## New: real dataset ML lab

The **Real dataset ML lab** link opens a separate trained-recognition mode. It uses ESC-50 recordings, with 1,200 training clips, 398 validation clips and 400 held-out test clips. The baseline achieved **42.75% classification accuracy**, so recognition remains limited. This is separate from the paper's synthetic DEDA results. Upload a WAV or choose a test recording to see actual predictions and warning decisions. Default cues are general; optional direction is explicitly simulated. The first prediction needs 1,024 ms of audio, so this mode does not meet a 300 ms onset target. [Full instructions](REAL_AUDIO_ML_GUIDE.md).
