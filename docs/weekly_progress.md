# Progress Report — Indoor Navigation Project

**Date:** 2026-07-07
**Deadline:** 2026-07-22
**Team:** three members (roles to be filled in the protocol)

This report summarises, in plain language, the progress made so far on the indoor
navigation project and what remains to be done.

---

## 1. What the project is

We are building a system that estimates where a person is (and which floor they are
on) as they walk through the two-floor EMI building, using only a smartphone in the
trouser pocket. The phone records:

- **motion** from its built-in sensors (accelerometer, gyroscope),
- **Bluetooth (BLE) beacon signals** — the strength (RSSI) of the fixed beacons it
  hears, and
- we additionally give the system **knowledge of the building layout** (corridors,
  doors, staircases).

The system fuses these three information sources with **one filtering method from
the lecture**. We chose a **particle filter**, and we evaluate the result against
the **door timestamps** we recorded during the four measurement runs.

---

## 2. Why a particle filter

We chose the particle filter over the Kalman filter because our problem is a
person confined to narrow corridors on two floors, with hard building constraints
and noisy Bluetooth signals. A particle filter handles this naturally: it keeps
many candidate positions ("particles") at once, can simply discard or down-weight
any that would sit inside a wall or on the wrong floor, and can represent several
competing guesses at the same time. The assignment itself notes that building
constraints are easier to model this way. Our recordings are short and processed
offline, so the extra computation is not a concern.

---

## 3. The data

We recorded **four runs**, each starting from a different position and each crossing
between the two floors at least once, covering straight walks, turns, different
speeds, and areas of good and poor beacon coverage. Each run is one file containing
several data streams (motion samples, Bluetooth readings, and a raw device scan).

Key facts we established while exploring the data:

- Only **6 of the 8 installed beacons** are ever heard (the east-wing pair is not
  on any of our paths), so the system uses those six.
- Bluetooth readings arrive **irregularly**, with occasional multi-second gaps,
  while the motion sensor is almost continuous.
- One run (Run 2) was **accidentally a duplicate** of another in the first
  submission; it has been replaced with the correct recording, which we verify
  automatically.

---

## 4. What has been built so far

The project is developed in small, verifiable milestones. Milestones **0 through 5
are complete**; the remaining work is evaluation and the final write-up.

| Stage | What it does | Status |
|-------|--------------|--------|
| Data understanding | Explore the raw recordings; document the runs and building | ✅ Done |
| Preprocessing | Clean and time-align the sensor streams | ✅ Done |
| Building model | Represent corridors, doors, beacons, and staircases | ✅ Done |
| Motion model | Detect steps and estimate walking direction | ✅ Done |
| Bluetooth model | Turn signal strength into position evidence | ✅ Done |
| **Particle filter** | Fuse motion + Bluetooth + building into a position estimate | ✅ Done |
| Evaluation | Measure accuracy against the door references | ⏳ Next |
| Final notebook | Assemble the reproducible report + related work | ⏳ To do |

### The motion model
We detect each step as a spike in the acceleration (about **1.4 steps per second**,
which is realistic), and we estimate the walking direction from the gyroscope. A
"dead-reckoning" path built from steps alone drifts over a few minutes — as
expected — which is precisely why we add the map and Bluetooth corrections.

### The particle filter (the core)
We built it in four stages so each part could be checked on its own:

1. **Motion only** — the cloud of guesses moves with each step and spreads out.
2. **+ Building map** — guesses are pushed back onto the corridors.
3. **+ Bluetooth** — a strong signal from a beacon pulls the estimate towards it,
   giving the absolute reference the map alone lacks.
4. **+ Floor changes** — guesses can switch floor only at a staircase, and the
   Bluetooth signals decide which floor is correct.

---

## 5. Two problems we found and fixed

Being honest about problems is part of the assessment, and finding them early is a
sign the step-by-step approach is working:

- **Distance scale was wrong.** Our first assumed step length made the estimated
  path about **1.7× too long**, so the estimate overshot every corridor. Measuring
  a known corridor stretch against the door timestamps gave the real value, and
  correcting it **roughly halved the position error on every run**.
- **Starting direction was wrong for some runs.** The gyroscope only gives *changes*
  in direction; the absolute starting direction depends on how the phone sat in the
  pocket and differs per run. We now calibrate each run's starting direction from
  its first straight corridor segment.

---

## 6. Preliminary results

These are early numbers (the formal evaluation is the next milestone), measured
against the recorded door positions:

- **Position error** at the door checkpoints is about **3–4 m on the best run** and
  larger (up to ~15–20 m) on the harder runs.
- **Floor is identified correctly about two-thirds of the time on average**
  (ranging from ~0.47 to ~0.88 across runs).
- Each fusion component behaves as intended: motion alone drifts, the map keeps the
  estimate on the corridors, and Bluetooth provides the absolute anchor.

### Honest limitations (to be discussed)
- Bluetooth is **coarse** indoors (multipath, only three beacons per floor), so it
  corrects position only approximately.
- When the position drifts, the estimate can **miss a staircase**, which delays or
  prevents the correct floor change.
- Two of the four runs are **weakly anchored** (a very short first corridor segment,
  and a run that only walks the ground floor at the very end).

None of this is unexpected — the assignment explicitly states that a perfect system
is not the goal; what matters is a sound method and an honest evaluation.

---

## 7. Deliverables in place

- **Modular, readable code**, one responsibility per file (data cleaning, building
  model, motion model, Bluetooth model, particle filter, plotting).
- **Reproducible notebooks** that run end-to-end and show the results of every
  completed stage (data exploration, preprocessing, step detection, and the full
  particle filter), so progress is continuously visible.
- **Written documentation**: an experimental protocol, a decision log recording
  every design choice and its justification, an architecture overview, and this
  implementation plan.

---

## 8. What is next

- **Evaluation (Milestone 6):** formal accuracy metrics against the door references
  (position error, floor accuracy, stability across runs) and comparison
  experiments showing what each fusion component contributes.
- **Final report (Milestone 7):** assemble the submission notebook covering all
  required sections, plus a short related-work discussion using three scientific
  sources.

We are on track for the 2026-07-22 deadline, with the hardest part (the particle
filter) already working.
