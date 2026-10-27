# SoundScape Project Teaching Guide

## Start here

This guide explains the project you are presenting: **a simulation study of how to turn uncertain sound information into useful directional warning commands**.

Your submission is simulation-only. You are presenting a report, a research paper and numerical simulation software. You are not presenting a completed physical band, a deployed sound-recognition product or a user-tested safety device.

If time is short, read sections 1–4, practise section 8, and learn the answers in section 14.

### Your project in one sentence

> We built a simulation to study when a sound-alert system should indicate a direction, give a general warning, or wait for more evidence.

### Your project in three sentences

> SoundScape Band is the proposed application: a band that could communicate sound warnings through four vibration points. Our current work is a simulation of the decision-making behind those warnings, using an algorithm called DEDA. We test whether checking direction reliability reduces misleading direction commands, and what that costs in delay, missed warnings and false alarms.

### The five things you must remember

1. **What is the sound?** and **where is it coming from?** are separate questions.
2. A believable sound label does not automatically make its estimated direction correct.
3. DEDA can accept the sound class while leaving out an uncertain direction.
4. The results are synthetic. They do not establish real-world wearable performance.
5. DEDA reduces wrong directions in our main test, but it also increases late warnings. We report both.

---

## 1. What problem are we studying?

Imagine a warning system says, “A vehicle horn is coming from your left.”

There are two ways that message can be wrong:

- It may not be a horn at all.
- It may be a horn, but the direction may be wrong.

The second problem matters because the system may direct attention away from the sound.

An alternative message is:

> A possible important sound has been accepted, but the system does not trust its direction enough to point somewhere.

In our simulation, that becomes a **general warning**, represented by all four virtual motors.

The research question is whether this choice reduces misleading directional commands, and whether the extra checks and waiting create other problems.

Deaf and hard-of-hearing people have different hearing experiences and preferences. We have not tested whether these proposed cues are useful or understandable for particular users.

## 2. What exactly have we built?

| Part | What it does |
| --- | --- |
| Browser simulation | Lets us choose a scene, calculate its direction and warning decisions, and inspect the result. |
| Python direction estimator | Uses the three synthetic microphone signals to estimate an angle. |
| DEDA policy | Decides whether to issue a directional warning, general warning, wait or reject. |
| Baseline policies | Provide simpler decisions for a fair comparison. |
| Batch experiment scripts | Run many repeatable synthetic cases and produce statistics. |
| Expanded synthetic dataset | Contains generated inputs and saved outcomes, with seeds and settings for reproduction. |
| Report and paper | Explain the method, results, trade-offs and limitations. |

The web page is connected to Python. It is more than a drawing of a band: Python calculates the direction and runs the decision policy.

However, the microphone inputs are generated signals and the sound-class scores are simulated inputs. The screen does not represent a physical wearable sensing your room.

### What the current submission does not contain

- A working physical three-microphone band.
- A trained sound classifier inside the web simulation.
- Real synchronized wearable recordings.
- Measured motor vibration, battery use or microcontroller execution time.
- A participant study or demonstrated user benefit.

There is older Android-app work in the project history. It is outside this simulation-only submission and is not evidence for the results in the current paper.

## 3. Understand the complete flow

There are **two inputs to the decision policy**, not one magical recognition step.

```text
Chosen sound scene
        |
        v
Generate synthetic sound and three microphone signals
        |
        v
Estimate sound direction using GCC-PHAT
        |
        v
Calculate direction-reliability checks -----------------+
                                                       |
Separately supply scripted sound-class scores ----------+
                                                       |
                                                       v
                                               DEDA decision policy
                                                       |
                          +----------------------------+------------------+
                          |                            |                  |
                          v                            v                  v
                 Directional warning            General warning      Wait or reject
                 One or two motors               All four motors
```

### Which parts are calculated, and which are supplied?

**Calculated from the synthetic microphone signals:**

- Time differences between microphones.
- Estimated direction.
- Closure, plane-wave norm and PHAT coherence.

**Supplied as a separate simulated input:**

- The class-score vector: horn, siren, shout, reversing beep and ambient.

**Calculated by DEDA:**

- Whether to accept the class evidence.
- Whether to trust the direction evidence.
- When to emit a warning and which virtual motor bits to select.

The selected scene also gives us the **ground truth**: the direction we used to generate the signal. We compare the estimated output against that known reference. The estimator does not simply copy the direction slider.

## 4. What DEDA adds

**DEDA means Dual Evidence Deadline Alerting.**

| Word | Simple meaning |
| --- | --- |
| Dual evidence | Keep evidence about sound class and direction separate. |
| Deadline | Limit how long an evidence episode can keep waiting. |
| Alerting | Decide whether and how to issue a warning command. |

An everyday analogy: a person may be confident that an alarm is sounding but unsure which room it is in. It can make sense to warn people without confidently naming a room.

DEDA applies a similar separation at the decision level.

| Class accepted? | Direction trusted? | Possible decision |
| --- | --- | --- |
| Yes | Yes | Give a directional warning. |
| Yes | No | Wait briefly if allowed, then give a general warning; urgency can bypass waiting. |
| No | Yes | Direction alone does not establish an important sound. Continue gathering evidence or reject. |
| No | No | Continue gathering evidence or reject. |

A later trustworthy direction may refine an earlier general warning.

### What is established work, rather than our novelty?

GCC-PHAT, time-difference estimation, coherence, geometric consistency and circular averaging already exist. We reuse them.

The proposed contribution is their use within a policy that separates class acceptance from spatial acceptance, allows a general fallback, and makes the consequences measurable.

Say:

> Our contribution is at the warning-decision level. We are not claiming to have invented GCC-PHAT or a new sound-recognition model.

Do not claim that the full policy is better than every uncertainty-aware method. Our own results show that simpler alternatives can be preferable on some measures.

## 5. Technical terms in everyday English

### Three microphones and TDOA

The same sound reaches microphones at slightly different times. These tiny differences help estimate its direction.

**TDOA** means **time difference of arrival**.

The reference array is a triangle with sides of 35 mm. That is an assumed virtual geometry, not a measured wearable. The expanded acoustic study also tests 25 mm and 50 mm triangles.

### GCC-PHAT

Think of sliding two signal patterns past each other to find their best time alignment. GCC-PHAT estimates that shift while reducing the influence of differences in frequency magnitude.

The three pairwise delay estimates are then used with the microphone geometry to estimate an angle.

You do not need to derive the signal-processing formula during the presentation. Know its role: **estimate delays, then direction**.

### Closure

We have three microphone pairs. Their estimated delays should agree around the triangle: in the ideal case, the signed delays add to zero.

The closure value measures disagreement. Our default gate allows a residual of at most **0.75 sample**.

Passing closure does not prove a direction is correct. In particular, constant channel offsets can cancel around the loop.

### Plane-wave norm

The estimated delays are fitted to a simple sound-propagation model. The norm should be reasonably close to one under that model.

Our default accepted range is **0.60–1.40**.

Think of it as a model-fit check, not a percentage accuracy score.

### PHAT coherence

This is a measure of how strongly the pairwise delay estimates are supported by the signal alignment.

The per-window minimum is **0.30**. A single direction window needs a stronger value of **0.50** for the policy's single-window acceptance route.

It is not a calibrated probability that the angle is right.

### Strongest 25% of frequency bins

A sound contains different frequency components. Some contain useful source information, while others may be dominated by noise.

The strongest-bin option uses the strongest quarter of cross-power bins in the selected band. The control uses all bins.

This helps some tested signals, but it does not solve all competing-source or timing errors.

### Circular averaging

Angles wrap around: 350° and 10° are both close to the front. Their useful average is near 0°, not 180°.

The policy combines directions as vectors around a circle and checks how consistently they point together.

### Class score

In the browser, a 95% horn score is **a chosen input to the policy**. It does not mean a trained model recognized a real horn with 95% accuracy.

The larger policy dataset also generates class-score sequences instead of running a trained recognizer.

### Window and hop

A window is a small piece of signal being analyzed. The browser uses **64 ms analysis windows**, advancing by a **64 ms hop**.

The simulation makes decisions repeatedly rather than examining the whole scene only once.

### Seed

A seed controls the pseudorandom generator. Repeating a seed with the same settings recreates the same numerical scenario.

A seed is not an audio recording, participant or physical recording session.

### Fallback

A fallback is the more general output used when the class has been accepted but the direction has not.

Here it means a virtual command to all four motors. It does not mean that physical vibrations have been measured.

### Ablation

An ablation disables one part of the method and runs the comparison again.

For example: remove the direction gate and check what happens to wrong directions, timing and false alerts.

## 6. The deadline without confusing yourself

We use **300 ms as an engineering reference**, with an assumed **60 ms processing allowance**.

The normal horizon is calculated as:

```text
K = max(0, floor((300 - 60) / 64) - 1)
K = 2
```

This allows up to two additional evidence steps after the opening step in that episode.

However, an event may take time to build enough class evidence to open an episode. Episodes may reject and reopen. Suppression can also affect outputs.

Therefore:

> A bounded evidence episode is not a guarantee that every sound receives a warning within 300 ms of its onset.

Our expanded results actually exceed that target in some cases. Physical acquisition, processing and motor activation are not measured.

### The browser's horn example

The default horn starts at **192 ms** on the scene clock.

The first DEDA warning occurs at **320 ms**.

```text
Warning delay = warning timestamp - sound onset
              = 320 - 192
              = 128 ms
```

The timeline reading of 320 ms and the summary reading of 128 ms describe different quantities. Neither is page-load time.

## 7. Know what every important screen control means

| Control or display | What to understand |
| --- | --- |
| Sound | Chooses a procedural sound surrogate; it is not listening to your room. |
| Direction | Sets the known source angle used to generate the scene. |
| SNR | Changes signal strength relative to noise. Higher means cleaner relative to the noise. |
| Condition | Selects a synthetic disturbance such as interference or direction dropout. |
| Class score | Supplies the class evidence independently of acoustic SNR. |
| Reproducibility settings | Seed, bin selection and sound duration. |
| Run scene | Recalculates results after changing settings. |
| Settings-changed notice | Warns that the visible results belong to the previous settings. |
| DEDA first warning | Delay of the first associated DEDA alert from source onset. |
| Direction outcome | Shows a matched direction, wrong direction, general warning or no accepted warning. |
| Current window | Reliability values and policy state at the selected replay time. |
| Last commanded motors | Keeps the last command visible for inspection. |
| Timeline and arrows | Inspect computed windows; they do not change the saved calculations. |
| Window-by-window decisions | Lets you inspect exactly when evidence was accepted, waiting or rejected. |
| Run JSON / Window CSV | Downloads the numerical evidence. |

Directions are relative to the wearer:

```text
             Front = 0°
                  |
Left = 270° ------ + ------ Right = 90°
                  |
              Back = 180°
```

The virtual motor letters are **F, R, B, L**. Near a quadrant boundary, DEDA may select two neighbouring motors instead of pretending the direction is exact.

### Two screen behaviours that are easy to misunderstand

**The sound has ended, but a motor is still highlighted.**

The display retains the last commanded motor so you can inspect it. It is not a physical vibration-duration model.

**The checks say “Pass”, but there is no directional alert yet.**

The current window's three checks are only part of the policy. Class evidence, direction aggregation and the episode state also matter.

## 8. Your final-review demonstration

### Before you start speaking

1. Open the project folder: `C:\Users\Rishit\Desktop\PROJECTS\soundscape-band`.
2. Double-click `Start-Simulator.cmd`.
3. Keep that terminal window open.
4. Open **http://127.0.0.1:8765** in the browser.
5. Confirm **Python engine connected**.

Fallback launch from PowerShell:

```powershell
cd C:\Users\Rishit\Desktop\PROJECTS\soundscape-band
python python\simulator_server.py
```

Do not open `index.html` directly. It needs the Python server.

### Opening statement — about 30 seconds

> Our current submission is a simulation study. The browser generates virtual microphone signals, calculates a direction, supplies scripted class scores, and runs the DEDA warning policy. We will show a clear-direction case, an uncertain-direction case and an uncertain-class case, then connect those behaviours to our larger numerical evaluation.

### Step 1 — Horn behind

Select **Horn behind**. The initial scene may already be displayed.

With the current seed-7 preset, the expected result is a **Back** warning after **128 ms** from onset. Baseline B warns after **64 ms**.

Say:

> We generated the horn behind the virtual wearer. Python estimates its angle from the microphone signals, and DEDA commands the back motor. In this clear scene the baseline is faster. DEDA's purpose is to investigate reliability trade-offs, not to be faster in every scene.

Point to the true source, estimated angle and three reliability values.

### Step 2 — Inspect the decision

Click **Jump to first warning**, then use the previous-window arrow or a row in the decision table.

Say:

> These are actual computed policy states. We can inspect the window before the warning and the window where the warning was emitted. The source starts at 192 ms, so the 320 ms scene timestamp corresponds to a 128 ms warning delay.

Show the waveform panel briefly. Explain that these are generated microphone signals.

### Step 3 — Siren left

Select **Siren left**.

The current seed-7 preset gives a **Left** warning after **64 ms**.

Say:

> The same pipeline also handles a different source surrogate and direction. The preset is repeatable; it is not a real-world accuracy measurement.

### Step 4 — Direction dropout

Select **Direction dropout**.

The current preset gives a **general four-motor warning after 192 ms**.

Say:

> Here we deliberately remove the direction observations. The class evidence can still be accepted, so the policy gives a general warning instead of inventing a direction.

This is an explicit fault injection. It does not mean the system detected real body shadowing or proved that every bad direction will be caught.

### Step 5 — Uncertain class

Select **Uncertain class**.

The preset uses score **0.30** and should produce **no accepted warning**.

Say:

> This is the other side of the separation. A direction estimate alone does not prove that an important sound is present. The class evidence in this preset is not accepted.

Do not describe this as guaranteed rejection of all false sounds.

### Step 6 — Ambient only

Select **Ambient only**.

Say:

> This is a simple control scene with a scripted ambient-class input. It should produce no warning. It is not enough exposure or variety to establish a low real-world false-alarm rate.

### Step 7 — Show the checklist and export

Open **Review checklist**, select **Run review cases**, and compare expected and observed behaviour.

Select **Inspect scene** to show one exact trace, or download **Evidence JSON**.

Say:

> These five checks confirm five specified simulation behaviours. Five out of five is not a recognition-accuracy score.

### Optional — Competing sources

Select **Competing sources** if you have time. Inspect what actually happens; do not promise a correct direction before calculating it.

Say:

> This is a difficult case. A coherent second source can produce a wrong but internally consistent direction. Our larger study also tests this failure, and we do not claim the checks solve it.

### Optional — A small experiment

Open **Experiments**, choose **Quick** and **1 seed**, then select **Run experiment**.

This runs **32 critical cases plus one ambient control: 33 total trials**.

Point to progress, the results table and the JSON/CSV export. **Cancel experiment** stops between trials and does not publish partial rates.

Use this only if the review has enough time. The five main scenes already explain the policy clearly.

## 9. The most important alignment issue

**The browser experiment and the paper's expanded evaluation are different experiments.**

| Evidence source | What it studies | How to describe it |
| --- | --- | --- |
| Browser scenes and Quick/Full experiments | Connected synthetic audio, direction estimation and policy behaviour with default settings and scripted scores. | An inspectable demonstration and acoustic stress suite. |
| Main paper evaluation | 100 generated class-score/direction streams, with frozen study thresholds. | A decision-policy comparison on 3,594 synthetic events. |
| Expanded acoustic study | 4,200 synthetic microphone scenes, each analyzed with two bin choices. | A paired front-end test of direction estimates and reliability gates. |

The paper's policy-stream inputs do **not** run GCC-PHAT for each event. The separate acoustic test evaluates that front end. The browser connects the stages for scene inspection but does not run a trained classifier.

The paper uses frozen class thresholds derived from historical synthetic calibration selections. The browser uses the engine's default configuration. The inputs, class-score patterns and test sizes also differ.

Therefore, running Quick in the browser is **not** supposed to reproduce the paper's 20.31% and 2.45% rates.

If a reviewer asks why the numbers differ:

> The on-screen experiment is a different acoustic suite and operating point. The paper's headline results come from the separately documented batch study. We keep the datasets and settings separate rather than mixing their figures.

## 10. Understand the expanded dataset

### Main decision-policy dataset

- **100 new streams**, seeds 3001–3100.
- Each stream represents **20 simulated minutes**.
- Total main exposure: **33.33 simulated hours**.
- Total critical events: **3,594**.
- The events are evaluated by **13 policies or variants**.
- This produces **46,722 event-policy rows**, not 46,722 independent events.

A stream is a generated sequence of class scores and direction observations. It is not a microphone recording.

### Stress and deadline sets

There are seven stress conditions, each with 30 streams. They vary how often bad directions are flagged, short-event duration, class-score correlation, plausible wrong directions and direction dropout.

A separate set of 30 streams tests the three deadline targets.

Together with the main set there are **340 condition–seed stream realizations** and **113.33 generated hours**. Some seed IDs are reused across stress conditions, so these are not 340 independent real recording sessions.

### Acoustic dataset

The acoustic study contains:

```text
7 conditions × 3 microphone spacings × 2 noise levels
             × 2 source types × 50 seeds
= 4,200 synthetic scenes
```

Each scene is tested with all bins and strongest 25% bins:

```text
4,200 scenes × 2 bin choices = 8,400 direction estimates
```

The source types are broadband noise and a harmonic horn-like surrogate. Both are tested at every seed direction.

Conditions include a competing source, a delayed-copy reflection surrogate, a timing offset, correlated microphone noise, gain mismatch and simplified source motion.

Gain mismatch is not body shadowing. One delayed source copy is not a validated reverberant room. The motion surrogate does not reproduce all physics of a moving sound source.

## 11. Main results to learn

These are the **expanded 100-stream study**, not the browser's Quick experiment.

| Measure | Baseline B | DEDA | What this means |
| --- | --- | --- | --- |
| Wrong-direction events | 20.31% | 2.45% | DEDA gives fewer misleading directional first commands. |
| Missed events | 0.17% | 0.17% | Rounded values are similar; this is separate from lateness. |
| Missed or late events | 10.19% | 15.32% | DEDA is worse on this timing measure. |
| General first warnings | 1.4% | 14.1% | DEDA more often leaves out a direction. |
| False alerts per ambient hour | 306.4 | 286.8 | The burden is high for both; this is not acceptable-deployment evidence. |
| Conditional angular error | 33.0° | 13.7° | Error among directional first detections; general warnings are excluded. |
| Mean stream p95 simulated latency | 369 ms | 413 ms | DEDA exceeds the 300 ms reference. |

Rates are means of per-stream rates. The general-warning row uses detected events as its denominator, while wrong-direction and missed-event rows use all critical events. Do not add the percentages as if they were one partition.

### The result in a balanced sentence

> DEDA reduces wrong-direction events in our synthetic test, but it gives more general warnings and increases missed-or-late events. We therefore report a trade-off rather than claiming overall superiority.

### What to remember if you forget every other number

- **20.31% to 2.45%**: wrong-direction events decrease.
- **10.19% to 15.32%**: missed-or-late events increase.
- **413 ms**: the mean stream p95 is above the assumed target.

The earlier **23.5% to 2.7%** result belongs to the historical four-stream simulation. It is background, not the expanded result and not a real-device result.

## 12. What the baseline and ablation tests teach us

### Baselines

| Name | Simple explanation |
| --- | --- |
| A | Accept the class at a fixed threshold and give a general warning. Never provide a direction. |
| B | Accept the class at the same threshold and use the raw direction. |
| G | Reject a prospective warning when the direction fails the gate. |
| F | Give an immediate general warning when direction fails the gate. |
| DEDA | Separate the two evidence streams, accumulate evidence and allow bounded waiting/fallback. |

Baseline A can have zero wrong-direction alerts simply because it never points anywhere. This is why wrong-direction rate alone cannot identify the best system.

### Ablations

The larger study also removes reliability checks, individual gates, sequential evidence, direction waiting and fallback. A single-motor DEDA version removes the two-motor boundary allowance.

Important findings:

- Without reliability, wrong-direction events rise from **2.45% to 7.96%** in the generated stream model.
- Without sequential evidence, warnings become more timely, but false alerts rise to about **1,782 per ambient hour**.
- Without direction waiting, wrong-direction events are **2.05%** and missed-or-late events **13.86%**, both lower than full DEDA. However, general warnings rise to about **21.0%**.
- A single-motor DEDA control gives **3.02%** wrong-direction events. Two-motor tolerance explains part, but not all, of the benefit over B.

The conclusion is not that every component always helps. It is that the components change different parts of the trade-off.

Some ablations change more than one behaviour: disabling sequential evidence also removes the waiting opportunity, for example. We disclose that rather than calling every result a perfectly isolated cause-and-effect test.

### A failure you should be prepared to explain

If directions are consistently wrong by 180° but look geometrically plausible, the checks can pass. The constructed decision-stream test gives about **99.7% wrong-direction events**.

In the paired acoustic study, about **83.4% of gate-valid strongest-bin estimates are wrong** in the competing-source condition.

Say:

> Agreement with the assumed geometry is not proof that the estimate follows the intended source. That is a known failure case in our results.

## 13. Metrics and statistics without difficult maths

### How we match an alert to an event

An event has a known generated start, end, class and direction.

We look for the first non-update alert from its start until **500 ms after its end**. That first alert defines its timing and direction outcome.

Updates do not establish first detection. A wrong-class alert can count as detected for the class-agnostic timing metric, so class correctness is evaluated separately.

### What each metric means

| Term | Everyday meaning |
| --- | --- |
| Wrong-direction event | The first directional command excludes the event's true quadrant. |
| Missed event | No first alert appears in the matching interval. |
| Missed or late | No first alert, or it arrives more than 300 ms after onset. |
| False alert | A non-update alert that does not match any critical event. |
| False alerts per ambient hour | False alerts adjusted for the amount of time outside event/grace intervals. |
| Angular error | How far the estimated angle is from the true angle, accounting for wrap-around. |
| General-warning fraction | The share of detected events that get a general first warning. |
| p50 | The median delay: half of detected delays are below it. |
| p95 | Roughly 95% of detected delays are below it within a stream. Our table averages those stream p95 values. |

The false-alert matcher does not penalize additional alerts inside the same event. The full report also supplies total notification burden to expose outputs that this definition leaves out.

### Confidence interval

A confidence interval describes how an estimate varies under the sampling method and assumptions.

For example, DEDA's mean wrong-direction rate is **2.45%**, with a **95% bootstrap interval of 1.93%–3.01%**.

This does not mean a real wearable is guaranteed to be in that range. It describes variation across our synthetic streams.

### Paired comparison

Both policies receive the same input stream. We compare their outcomes on that same input, rather than giving one an easier dataset.

### Bootstrap

We repeatedly resample complete streams to estimate variability. We keep each stream intact because neighbouring windows are related.

For acoustic comparisons, we resample seed groups while keeping their layout, source-type and noise-level repetitions together.

### Why use more seeds?

One lucky seed can make a method look unusually good. More independent seeds help reveal typical behaviour under the generator.

They do not make an unrealistic generator realistic. More synthetic data cannot replace recordings when answering real-world questions.

## 14. Likely reviewer questions and simple answers

### 1. What did you actually build?

> A reproducible numerical simulation, a direction-and-warning decision pipeline, a browser interface for inspection, and expanded evaluation scripts and results.

### 2. Is there a real band?

> Not in this submission. The band is the proposed application; our current contribution is a simulation study.

### 3. Does the web page listen through a microphone?

> No. It generates synthetic microphone signals. The class scores are supplied separately as simulated inputs.

### 4. Why use simulation?

> It lets us control the true source, repeat exactly the same conditions, compare policies fairly and create known failure cases. Its limitation is that the assumptions may not match real environments.

### 5. Where is the machine-learning model?

> A trained recognizer is not part of this evaluation. We isolate the decision policy by providing generated class-score sequences. We do not claim recognition accuracy.

### 6. Is a 95% class score 95% accuracy?

> No. Here it is a chosen policy input, not a measured classifier performance result.

### 7. What is new if GCC-PHAT already exists?

> The proposed decision policy separates class and direction acceptance, allows spatial fallback and later refinement, and evaluates their costs. The front-end estimators are established methods.

### 8. How is this different from just rejecting uncertain predictions?

> DEDA can retain an accepted class warning while omitting the direction. Our G and F baselines test rejection and immediate fallback directly.

### 9. Is DEDA always better?

> No. It reduces wrong direction under the main generator but increases lateness. Immediate fallback and no-direction-wait variants are strong alternatives.

### 10. Why not simply warn with every motor?

> That avoids wrong spatial commands but never provides direction. Baseline A represents this option. We study the balance between spatial information and misleading guidance.

### 11. Why three microphones?

> The study uses a small triangular array to estimate a two-dimensional direction from pairwise delays. The third pair also supplies a consistency relationship. We have not proved that this is an optimal physical design.

### 12. Why 35 mm spacing?

> It is the reference geometry assumed by the project, not an experimentally optimized wearable spacing. We also test 25 mm and 50 mm layouts synthetically.

### 13. Can a wrong direction pass every check?

> Yes. Coherent interference or a plausible wrong delay pattern can pass. We include explicit counterexamples and report them.

### 14. Why is there no physical vibration?

> The circles represent motor commands. The simulation does not model motor rise time or a person's tactile experience.

### 15. Is 300 ms guaranteed?

> No. It is an engineering reference with an assumed processing allowance. The simulated latency results exceed it in some cases, and physical onset-to-vibration latency is not measured.

### 16. Why do the browser experiment numbers differ from the paper?

> They use different datasets and operating settings. The browser's acoustic suite is not the paper's 100-stream policy dataset.

### 17. Why does changing noise not change the class score?

> The class score is deliberately a separate scripted input. Noise changes the synthetic acoustic direction problem; there is no trained classifier linking the two in this simulator.

### 18. Are the 100 streams real recordings?

> No. They are generated score and direction sequences using fixed assumptions and independent seeds.

### 19. Did you test body shadowing or a real reverberant room?

> No. We use limited gain and reflection surrogates and label them as such. They do not establish performance on a worn array or in a real room.

### 20. Did the code run on RP2040 or ESP32?

> Not as a complete measured pipeline in this submission. We cannot claim target-board timing, energy or memory feasibility from host simulations.

### 21. Did you test with Deaf or hard-of-hearing participants?

> No. User benefit remains unvalidated. A later study would need intended-user involvement, ethics approval and informed consent.

### 22. Why are false alerts still so high?

> The generated streams include class confusers, and direction checks do not solve class recognition errors. The high burden is an important limitation, not a deployment result we consider acceptable.

### 23. Why does the easy ambient demo show no warning, while the study has many false alerts?

> The preset is a short, simple ambient control with a scripted ambient input. The larger stream generator deliberately includes difficult class-score confusers. They are different tests.

### 24. What would you improve next?

> First test more realistic and independently checked simulation models and the no-wait policy trade-off. Future real-world work would add disjoint recorded datasets, calibrated recognition, synchronized-array validation, target-board profiling and user evaluation.

### 25. What makes the work reproducible?

> We provide code, fixed parameters, seeds, per-stream results, event outcomes, acoustic estimates, reproduction commands and file checksums.

## 15. A short presentation script

Use this as a speaking aid, not something to read word for word.

> Our project studies directional warnings for the proposed SoundScape Band. A sound label and its direction can fail independently, so we should not automatically trust a direction just because the sound-class score is high.
>
> We evaluate DEDA, which keeps class and direction evidence separate. When both are accepted, it gives a directional command. When the class is accepted but direction is uncertain, it can wait within an evidence horizon and then give a general warning. All commands in this submission are virtual.
>
> Our browser simulation lets us inspect the computed microphone signals, angle, reliability checks and decision trace. The class scores are scripted, so this is not a live sound-recognition demonstration.
>
> The expanded main study contains 100 synthetic streams and 3,594 events. Wrong-direction events fall from 20.31% for raw fusion to 2.45% for DEDA, but missed-or-late events rise from 10.19% to 15.32%. We also report high false-alert burden and failures where wrong directions pass the checks.
>
> Our conclusion is a measured simulation trade-off, not a claim of a validated wearable. Hardware performance, real recordings and user validation remain future work.

Then move directly to **Horn behind**, **Direction dropout**, and **Uncertain class**.

## 16. Phrases to use and avoid

| Avoid saying | Say this instead |
| --- | --- |
| “We built a working safety band.” | “We built a simulation study for a proposed directional-warning band.” |
| “The AI recognized this horn at 95% accuracy.” | “The scene uses a scripted 95% class-score input.” |
| “The motor vibrates.” | “The display shows a virtual motor command.” |
| “The system always warns within 300 ms.” | “300 ms is a reference target; some simulated warnings are late.” |
| “DEDA is 97.55% accurate.” | “Its mean wrong-direction event rate is 2.45%; that is only one defined metric.” |
| “The checks guarantee the angle is correct.” | “They check consistency, and can accept a plausible wrong direction.” |
| “We recorded 100 sessions.” | “We generated 100 independent main streams.” |
| “We have 46,722 independent test events.” | “We have 3,594 events evaluated by 13 policy variants.” |
| “We proved the method helps Deaf users.” | “User benefit has not been evaluated.” |
| “The browser reproduces the paper's percentages.” | “The browser and paper use separately documented experiment settings.” |

## 17. Review preparation checklist

### Before the review

- Open the latest report and paper listed below; do not accidentally present an older manuscript with stronger hardware claims.
- Start the simulator and rehearse the five main presets.
- Practise explaining why 320 ms on the timeline can mean a 128 ms warning delay.
- Rehearse the difference between a general warning and no accepted warning.
- Save one scene JSON, one window CSV and the review-checklist evidence JSON as backup evidence.
- Keep a screenshot or exported summary as backup, clearly described as a saved result if used.
- Confirm Python and dependencies work before arriving. Internet is not required for the local demonstration once dependencies are installed.
- Keep the terminal open and the laptop powered during the demonstration.
- Agree who will explain the problem, who will demonstrate, and who will discuss evaluation. Allocate speaking roles without inventing claims about individual implementation work.

### During the review

- State the simulation-only scope at the beginning.
- Let the selected scene finish computing before explaining its outputs.
- After changing controls, select **Run scene** and watch for the settings-changed notice.
- Use a source-active window, preferably **Jump to first warning**, rather than interpreting a noisy ambient tail as a meaningful source direction.
- Explain what the actual output shows, including a failure or general warning.
- If asked for a measurement we do not have, say so directly and explain the appropriate future test.

### If the simulator does not open

| Problem | Action |
| --- | --- |
| Browser says Python unavailable | Start `Start-Simulator.cmd`, then use Reconnect or reload. |
| HTML opened as a local file | Use `http://127.0.0.1:8765`, not a file address. |
| Port 8765 is already used | Check for an existing simulator. Otherwise use the alternate-port command below. |
| NumPy is missing | Before the review, install dependencies with the same Python interpreter that starts the server. |
| No warning at low class score | This can be the expected rejection. Inspect the trace. |
| Another computation is running | Wait for completion or cancel the experiment before starting a scene. |
| Unexpected competing-source result | Inspect and explain it as a stress result; do not force a successful direction. |

Alternate port:

```powershell
python python\simulator_server.py --port 8766
```

Then open **http://127.0.0.1:8766**.

Dependency setup, if needed before the review:

```powershell
python -m pip install -r requirements.txt
```

Do not start a long dependency installation or the entire research study in the middle of the presentation.

## 18. Files and commands you should recognize

| File | Role |
| --- | --- |
| `Start-Simulator.cmd` | Starts the local demonstration server. |
| `simulator/index.html`, `style.css`, `app.js` | Browser layout, appearance and interaction. |
| `python/simulator_server.py` | Connects the browser to the simulation engine. |
| `python/deda/simulator.py` | Generates browser scenes and runs the connected acoustic/policy calculation. |
| `python/deda/doa.py` | Synthetic array model and GCC-PHAT direction calculation. |
| `python/deda/policy.py` | DEDA, baseline decisions and suppression logic. |
| `python/deda/synth.py` | Generates the policy-study score and direction streams. |
| `python/deda/metrics.py` | Matches alerts to events and calculates shared evaluation metrics. |
| `python/final_simulation_study.py` | Runs the expanded main, stress, deadline and acoustic protocols. |
| `python/supplement_simulation_study.py` | Adds the single-motor control and acoustic cluster intervals. |
| `results/final_simulation_study/` | Saved expanded study data, settings and results. |

The following commands reproduce the research study. They are for preparation or independent verification, not necessary for the short browser demo:

```powershell
python python/final_simulation_study.py --workers 4
python python/supplement_simulation_study.py
python python/test_final_study.py
```

The study specifies Python 3.12 and NumPy 2.3.5. Its pinned numerical dependency is in `requirements-study.txt`.

To regenerate one complete score/direction stream:

```powershell
python python/final_simulation_study.py --export-stream 3001
```

## 19. Current submission files

Use these updated simulation-only versions:

- [Final simulation report — 15 pages](submission/SoundScape_Final_Report_Updated.docx)
- [Research paper — 5 pages](submission/SoundScape_Final_Research_Paper_Updated.docx)
- [Synthetic dataset and reproduction instructions](../results/final_simulation_study/README.md)

The report's final appendix maps the teacher's concerns to the changes and the remaining scope boundaries.

## 20. Your last-minute revision card

Read this immediately before presenting:

> **What did we do?** Built and evaluated a repeatable simulation of directional warning decisions.
>
> **Main idea?** Separate “what sound?” from “which direction?”.
>
> **If direction is uncertain?** Retain an accepted class as a general warning instead of inventing a direction.
>
> **What is computed?** Synthetic signals, delay/direction estimates, reliability checks and policy decisions.
>
> **What is supplied?** Generated class scores; no trained recognizer is being evaluated.
>
> **Main dataset?** 100 streams, 3,594 events; separate acoustic study: 4,200 scenes.
>
> **Main finding?** Wrong directions decrease, but late/general warnings and false-alert burden remain important costs.
>
> **Big limitation?** Synthetic assumptions, no real wearable or user validation, and plausible wrong angles can pass the checks.
>
> **Demo sequence?** Horn behind → inspect trace → siren left → direction dropout → uncertain class → ambient → review checklist.
>
> **Final claim?** A reproducible simulation trade-off, not a proven real-world safety product.


## 21. Explain the current audible browser simulation

Say: "The sound you hear is the same generated microphone-1 signal used by our direction calculation. Class scores are still scripted. We can hear a sound without having enough class or direction evidence to issue a warning."

Use **Hear & watch** to enable sound, then **Presentation mode** to focus on the wearer and explanation. **Next demo case** advances through horn, siren, missing direction, uncertain class and ambient. **Run scene** always recomputes the settings and starts replay from the beginning, using the current sound on/off setting. Initial page loading and preset computations can remain paused for inspection.

Replay speeds are **0.25×, 0.5×, 1× and 2×**. Slowing the replay also lowers audio pitch. Use 1× to hear the normal generated signal, then 0.25× to explain individual decisions. Labels remain model milliseconds: a 128 ms decision does not become a measured 512 ms hardware delay at 0.25×.

The policy comparison cards show the last actual command of each policy at the selected time. In the default horn case, **Baseline warning** jumps to 256 ms on the model timeline, 64 ms after onset. DEDA has not warned yet. **DEDA warning** jumps to 320 ms, or 128 ms after onset. This illustrates additional evidence gathering, with a timing cost. The deadline is a maximum policy budget, not a required waiting time.

The evidence bars show post-step support for horn, siren, shout and beep. Positive scores support a class; negative scores oppose it. They are not percentages. Scores reset after an alert, so the alert window can show zero. Direction checks can pass on an incorrect but physically plausible angle. Read the true-source outcome as well as the checks.

The public browser simulation is now available at **https://soundscape-simulation.vercel.app** without a local server. Hosted experiments return results when complete; live progress, cancellation and reload recovery remain local-server features. To launch the local review setup instead:

```powershell
python python/simulator_server.py --port 8766
```

Open http://127.0.0.1:8766 on the same computer. The default launcher uses port 8765; either works when its URL matches the server's port.

## 22. Explain Wokwi alongside the browser

Say: "Our browser computes acoustic direction evidence from synthetic audio. Wokwi demonstrates the decision and output stage on a virtual ESP32. It takes prepared window inputs and runs the actual C DEDA policy. The buttons choose input cases; they do not directly choose the LED answer."

The Wokwi OLED explains the decision. LEDs represent motor commands: Front=1, Right=2, Back=4, Left=8, and all four=15. The five cases are horn behind (Back, 128 model ms), siren left (Left, 64 ms), missing direction (all four, 192 ms), uncertain class (no alert), and ambient (no alert).

Direction commands use an illustrative single light pulse; general warnings use double pulses on all four. The sketch displays each 64 ms model step every 650 ms so it is easier to watch. The light pattern and display speed are not physical vibration measurements or validated haptic encodings.

The replay/display sketch compiled for ESP32, but the complete acquisition, recognition and localization pipeline has not been validated on a physical board. Compiler storage/global-variable figures apply only to this sketch. Wokwi does not recognize a horn through a simulated microphone. The browser sound is not connected to a live Wokwi audio recognizer.

Use the [Wokwi setup guide](../wokwi/README.md) for the six files and pin connections. Both demos use the web engine's default class thresholds. The report's main numerical study uses its own separately frozen thresholds and larger dataset; do not combine their results.
