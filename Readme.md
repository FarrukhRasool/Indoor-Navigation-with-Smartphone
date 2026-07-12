# Indoor Navigation with a Smartphone, BLE Beacons, and IMU

A plain-English guide to **how we approach the problem** and **how the code
actually works**. Read this top-to-bottom and you should understand the whole
project. Part 1 is the ideas; Part 2 is the code, file by file; Part 3 walks
through what happens end-to-end; Parts 4–6 cover the filter in detail, the design
choices, and how to run it.

---

# Part 1 — The problem and how we approach it

## 1.1 What we are trying to do

A person walks through a two-floor building (the EMI building) with a smartphone in
their trouser pocket. From the phone's sensors alone, we want to estimate **where
they are** and **which floor they are on**, over time. There is no GPS indoors, so
we have to be clever about combining weaker clues.

We have three sources of information:

1. **Motion** — the phone's accelerometer and gyroscope tell us when a step is
   taken and roughly which way the person is turning.
2. **Bluetooth (BLE)** — the building has fixed beacons; the phone hears them with a
   signal strength (RSSI) that is stronger when the phone is closer.
3. **The building map** — we know the corridors, doors, and staircases, so we know
   which positions are even *possible*.

None of these is good enough alone. Motion **drifts** (small errors add up over
minutes). Bluetooth is **noisy** and only tells us roughly how close a beacon is.
The map doesn't tell us where we are, only where we *could* be. The whole idea is
to **fuse** them so their strengths cover each other's weaknesses.

## 1.2 The tool we use: a particle filter

We estimate the position with a **particle filter**. The intuition:

- Imagine we scatter **500 guesses** ("particles") about where the person might be.
  Each particle is a little pin on the map at some `(x, y)` and floor.
- **Every step**, we move *all* the particles forward by roughly one step in the
  person's direction — but each particle a little differently (some longer, some
  turned slightly), because we are not sure of the exact step. The cloud of pins
  **spreads out**, representing our growing uncertainty.
- Then we **score** each particle by how well it agrees with what we know:
  - a particle sitting in a wall gets a low score (the map),
  - a particle far from a beacon that we currently hear *loudly* gets a low score
    (Bluetooth).
- We then **resample**: keep and duplicate the high-scoring particles, drop the
  low-scoring ones. The cloud concentrates on the positions that make sense.
- Our **estimate** at any moment is the average of the cloud.

Over time this pulls the estimate towards the true path: motion keeps it moving,
the map keeps it on the corridors, and Bluetooth keeps nudging it towards the right
place. This is the standard "predict → weight → resample" loop of a particle filter.

**Why a particle filter and not a Kalman filter?** Because our constraints are
awkward: hard walls, discrete floor changes, and Bluetooth that can be ambiguous
(it might fit two different spots). A particle filter handles all of this naturally
— you just give bad particles a low score. A Kalman filter assumes smooth, single-
peaked uncertainty and struggles with walls and floor jumps. The assignment even
hints at this.

## 1.3 The map of the world

We describe the building with a simple **coordinate system**:

- origin at the **west staircase**, `x` points **east**, `y` points **north**, in
  metres;
- a separate **floor** number (0 = ground, 1 = above it);
- both floors share the same footprint: one long **corridor** plus a short stub to
  the east staircase.

We model the walkable space as a **centre-line with a half-width**: a point is
"walkable" if it is within ~1 m of the corridor line. This is much simpler than
drawing exact walls, and it is good enough for a corridor building.

Because we had no exact building dimensions, distances are **approximate** (derived
from a typical door spacing). That is fine — the filter only needs the distances to
be internally consistent, and Bluetooth + the door references anchor the scale.

## 1.4 How we know if it works: the door references

During each run, the person **stopped briefly at known doors** and we recorded the
time. Those door timestamps are our **ground truth**: at that moment we know
exactly where they were. To check the system, we compare our estimated position at
each of those times against the true door position, and measure the distance error.

---

# Part 2 — How the code is organised

The rule is **one job per file**, all inside `src/`. Nothing mixes concerns: the
Bluetooth file knows nothing about steps, the filter knows nothing about reading
files, and so on. Here is each file in plain English.

```
src/
├── preprocessing.py   # loads a run and cleans it into a "Run" object
├── imu.py             # motion: steps, walking direction, motion table
├── ble.py             # Bluetooth: clean readings + turn RSSI into particle scores
├── building.py        # the map: corridors, doors, beacons, staircases
├── particle_filter.py # the core: fuse everything into a position estimate
├── evaluation.py      # load the door references (metrics coming in M6)
└── visualization.py   # all the plots
```

## 2.1 `preprocessing.py` — get clean data

This is the **only place** that opens the raw CSV files. One run's file contains
several mixed streams (motion, Bluetooth, a raw device scan) stacked in one table,
told apart by a `source` column.

- `load_run(run_id)` is the one function everything else calls. It reads the CSV,
  splits it by stream, asks `imu.py` and `ble.py` to clean each part, gives every
  stream a **shared clock** (`t_rel` = seconds since the run started), collects some
  descriptive facts, and returns a **`Run`** object.
- A `Run` bundles: the cleaned `accel`, `gyro`, `mag` streams, the app's already-
  filtered IMU (`imu_processed`, kept only for comparison), the cleaned `ble`
  stream, and a `meta` dictionary of counts and quality facts.
- `RUN_START` holds each run's **known starting position and direction** (see
  §5). We are allowed to fix the start point, and the starting direction is
  calibrated per run.

Important design choice: **we do not merge motion and Bluetooth into one table.**
They stay separate but share the `t_rel` clock. This "event-driven" layout is
exactly what the filter wants: step forward on motion samples, and only apply a
Bluetooth correction at the moments a reading actually arrives.

## 2.2 `imu.py` — from raw motion to a "motion table"

This turns the shaky accelerometer/gyroscope signals into **per-step movement**.

- `detect_steps(accel)` — a step makes the phone shake, so the overall acceleration
  briefly spikes. We take the acceleration *magnitude* (which ignores how the phone
  is rotated) and find the **peaks**. Each peak is one step. We get ~1.4 steps per
  second, which is a realistic walking pace.
- `estimate_gravity_direction` + `heading_from_gyro` — the direction of travel. The
  gyroscope measures turning; we figure out which axis is "up" (from gravity), read
  off the turning rate around it, and add it up over time to get a **heading**
  (which way the person faces). We remove a small constant drift in the gyro, and we
  anchor the heading to the run's known starting direction.
- `build_motion_table(run)` — the key output. For **each step** it records: the time,
  an assumed **step length**, the **heading** at that moment, and an **uncertainty**
  on the heading. This "error-prone motion sector" is exactly what the filter needs.
- `dead_reckoning(motion_table)` — a diagnostic: just add up the steps with no map
  or Bluetooth. It drifts over a few minutes (that's expected) but its shape should
  look like corridor walking. It proves the motion model is sane before we filter.

## 2.3 `ble.py` — from signal strength to a particle score

Two jobs: clean the Bluetooth stream, and turn one reading into particle scores.

- `extract_ble_stream` — keep only the project beacons (named `arrive_emi*`), drop
  unrelated devices, keep the raw signal strength (no smoothing), on the shared
  clock.
- `rssi_likelihood(particle positions, beacon position, observed_rssi)` — the
  **observation model**. Given one reading ("beacon X was heard at strength −70"),
  it returns a **score for every particle**: how believable is that reading if the
  person were really where that particle sits? We use the standard **log-distance
  path-loss** idea: a beacon should be heard at a strength that depends on distance;
  we compare the strength we *would expect* at the particle's distance with the
  strength we *actually heard*, and score the particle higher when they match.
  - "Strong signal ⇒ near the beacon" comes out for free: a **loud** reading only
    fits particles **close** to the beacon (a tight, informative constraint), while
    a **weak** reading fits a large far-away region (barely informative). So strong
    readings are automatically weighted more, exactly as the assignment asks.
  - Beacons on the *other* floor are penalised, so Bluetooth also helps decide the
    floor.

## 2.4 `building.py` — the map and the rules

Pure geometry; it reads no data and runs no filter. It just answers questions.

- `corridor_polyline(floor)` — the corridor centre-line as a few points.
- `is_walkable(x, y, floor)` / `distance_to_corridor(...)` — is this point on a
  corridor, and if not, how far off is it?
- `door_positions()` — the metric `(x, y)` of every reference door.
- `beacon_positions()` — the metric `(x, y, floor)` of the six beacons.
- `can_change_floor(x, y)` — is this point inside a **staircase zone**? Floor changes
  are only allowed here.

## 2.5 `particle_filter.py` — the core (explained fully in Part 4)

Holds the particle filter, built up in four stages so each piece is testable:

- `run_motion_only` — stage 5a: motion only (the cloud spreads, no correction).
- `run_with_constraints` — stage 5b: add the map (score by walkability, resample).
- `run_with_ble` — stage 5c: add Bluetooth (multiply in the RSSI score).
- `run_filter` — stage 5d: the **full** filter, adding per-particle floor and
  staircase floor changes.

Helper pieces: `initialise_particles`, `predict` (move one step), `constraint_weights`
(map score), `rssi` scoring is called from `ble.py`, `maybe_change_floor`,
`effective_sample_size` + `systematic_resample_indices` + `resample` (the resampling
machinery), and `estimate` / `estimate_floor` (the point estimate).

## 2.6 `evaluation.py` — the ground truth (and, soon, the metrics)

- `load_reference(run_id)` — reads the door-timestamp spreadsheet into a tidy table:
  for each checkpoint, its number, floor, room, and the time on our shared clock.
- The **error metrics** (distance error at each door, floor accuracy, summaries) are
  the next milestone (M6); this file will grow to hold them.

## 2.7 `visualization.py` — all the plots

Every plot lives here and nowhere else. It only *draws* already-computed data (it
never computes anything). Examples: acceleration with detected steps, the heading
over time, the dead-reckoning path, the particle cloud, the trajectory on the
corridor, the estimated floor over time, and the trajectory split by floor.

---

# Part 3 — How it all connects (one run, start to finish)

For a single run, the pieces are used in this order:

1. **`preprocessing.load_run(id)`** → a clean `Run` (motion + Bluetooth on one clock).
2. **`imu.build_motion_table(run)`** → the per-step movement table (steps, lengths,
   headings).
3. **`building`** provides the corridors, door and beacon positions, and staircases.
4. **`evaluation.load_reference(id)`** → the door ground-truth on the same clock.
5. **`particle_filter.run_filter(run, motion_table, ...)`** walks through time,
   predicting on each step, scoring with the map and Bluetooth, resampling, and
   changing floor at staircases → an estimated trajectory `(t_rel, x, y, floor)`.
6. **`evaluation`** compares the trajectory with the door references → error numbers.
7. **`visualization`** draws the trajectory, signals, and errors.

The **notebooks** (`notebooks/01…05`, `Final_Report`) just orchestrate these steps
and present the results — they contain no logic of their own.

---

# Part 4 — The particle filter, step by step

This is the heart of the project, so here is exactly what `run_filter` does. Each
particle is a guess: a position `(x, y)`, a `floor`, and a weight (score).

**Setup.** Scatter `n = 500` particles around the known start position, all on the
known start floor.

**Then, for every detected step:**

1. **Predict (move).** Move each particle forward by roughly one step length in the
   step's heading — but each particle draws its *own* slightly different length and
   heading from the uncertainty. The cloud fans out into the "likely area of
   presence".
2. **Maybe change floor.** Any particle currently inside a **staircase zone** may
   flip floor (0↔1) with a small probability. This creates competing "we went
   upstairs" vs "we stayed" guesses; Bluetooth will settle it.
3. **Score by the map.** Give each particle a weight based on how walkable its
   position is — full weight on the corridor, quickly fading if it strays off. This
   is a **soft wall**.
4. **Score by Bluetooth.** For every Bluetooth reading that arrived during this step,
   multiply each particle's weight by the `rssi_likelihood` score for that beacon.
   Particles that "explain" the reading survive; others fade. Because each particle
   carries its own floor, readings from the wrong floor correctly punish particles
   on the wrong floor.
5. **Estimate.** Record the weighted-average position, and the majority floor, as our
   estimate at this moment.
6. **Resample when needed.** If a few particles dominate (measured by "effective
   sample size"), duplicate the strong ones and drop the weak ones. The next step's
   movement noise re-spreads them, keeping variety.

The output is the estimated path over time. Motion drives it, the map keeps it
plausible, and Bluetooth corrects its drift and decides the floor.

---

# Part 5 — Design choices and calibrations

We keep a full decision log in `docs/decisions.md` (entries D1–D12). The ones most
useful to understand:

- **Particle filter** chosen over Kalman (D1) — handles walls and floors naturally.
- **Coordinate system and corridor model** (D2, D3) — origin at the west staircase,
  corridor as a centre-line with a half-width.
- **Bluetooth model** (D7) — log-distance path-loss; strong signals weighted more.
- **Step length** (D10) — our first guess (0.70 m) made the path ~1.7× too long; we
  measured it against a known corridor stretch and corrected it to **0.50 m**, which
  roughly halved the error on every run.
- **Starting direction** (D11) — the gyroscope only gives *changes* in direction; the
  absolute start depends on how the phone sits in the pocket and differs per run, so
  we calibrate it from each run's first straight corridor segment (stored in
  `RUN_START`).
- **Floor changes** (D12) — allowed only at staircases; Bluetooth decides which floor.

A few **tunable knobs** live at the top of the files: the wall softness
(`WALL_SIGMA_M`), the floor-change probability (`FLOOR_CHANGE_PROB`), the Bluetooth
model parameters, and the movement noise. These let us trade responsiveness against
stability.

---

# Part 6 — How to run it

The notebooks are the easiest way in. From the `notebooks/` folder they add `../src`
to the path and import the modules. A minimal run of the full filter on Run 1:

```python
import sys; sys.path.append("../src")
import preprocessing, imu, building, ble, particle_filter as pf, visualization as viz
import matplotlib.pyplot as plt

run = preprocessing.load_run(1, raw_dir="../data/raw")
cfg = preprocessing.RUN_START[1]                       # known start position + heading
motion = imu.build_motion_table(run, initial_heading=cfg["initial_heading"])

trajectory, spread, n_resamples = pf.run_filter(
    run, motion, start=cfg["start"], floor=cfg["floor"],
    building=building, ble=ble, seed=0)                # seed => reproducible

viz.plot_trajectory_two_floors(trajectory, building.corridor_polyline(0),
                               building.CORRIDOR_HALF_WIDTH_M,
                               beacons=building.beacon_positions(), run_id=1)
plt.show()
```

The notebooks, in order:
`01_Data_Exploration`, `02_Preprocessing`, `03_Step_Detection`,
`04_Particle_Filter` (the core), and `05_Evaluation` + `Final_Report` (still
skeletons, filled in the next milestones).

---

# Part 7 — Where things stand

**Done:** data understanding, preprocessing, the building model, the motion model,
the Bluetooth model, and the complete particle filter (all four stages).

**Early results:** position error around 3–4 m on the best run (larger on the harder
runs), floor identified correctly about two-thirds of the time on average. These are
realistic for a coarse indoor system, and the honest limitations (noisy Bluetooth,
motion drift, approximate geometry) are documented.

**Next:** formal evaluation with the door references and comparison experiments
(Milestone 6), then assembling the final submission notebook with a related-work
discussion (Milestone 7).

---

# Where to look

| I want to understand… | Read… |
|-----------------------|-------|
| The plan and milestones | `docs/implementation_plan.md` |
| Why each choice was made | `docs/decisions.md` (D1–D12) |
| The runs, building, beacons, references | `docs/experiment_protocol.md` |
| The module responsibilities and data flow | `docs/architecture.md` |
| A professor-facing progress summary | `docs/weekly_progress.md` |
| The code itself | `src/` (one job per file) |
| Worked examples with outputs | `notebooks/` |
