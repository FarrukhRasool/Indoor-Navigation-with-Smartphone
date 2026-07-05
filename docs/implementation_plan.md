# Implementation Plan — Indoor Navigation (BLE + IMU + Building Constraints)

This document breaks the project into **milestones** that we complete step by
step. Each milestone lists its objective, concrete tasks, the modules involved,
inputs/outputs, the deliverable, and a clear **Definition of Done (DoD)** so we
always know when a stage is finished.

The plan is intentionally incremental: every milestone produces something
visible (a plot, a table, a working function) that we can show in the weekly
meetings, as the assignment requires.

---

## 0. Guiding principles

Carried from `CLAUDE.md` and the assignment:

- **One filtering method only.** We use a **Particle Filter** (see decision
  below). No mixing of methods.
- **Modular `src/`.** One responsibility per file. No cross-mixing of concerns.
- **Simple, readable, student-level code.** Correctness and clarity over
  cleverness. Implement one module at a time and review after each.
- **Sensor fusion is mandatory:** step detection + movement direction + BLE
  weighting + building constraints must all feed the estimate.
- **Evaluation is door-anchored.** The door reference timestamps are the
  ground truth; every result is judged against them.
- **Reproducible notebook** is the final deliverable (deadline **2026-07-22**).

### Key method decision — Particle Filter (recommended)

The assignment explicitly notes that building constraints (walls, corridors,
stairs, floor transitions) are "more directly and flexibly" modelled in a
particle filter, because invalid states can simply be discarded or
down-weighted. Our problem is exactly this: a person constrained to narrow
corridors on two floors, with non-linear map constraints and noisy RSSI.

- **Recommendation:** **Particle Filter.**
- **Why:** naturally handles the L-shaped corridors, wall constraints, discrete
  floor changes at staircases, and multi-modal position beliefs (RSSI alone is
  ambiguous). Easy to inject building constraints as particle weights.
- **Trade-off:** more particles = more compute, but our runs are short (3–4 min)
  and offline, so this is not a concern.
- **Status:** proposed — **needs the team's explicit confirmation** before M5.

---

## 1. Milestone overview

| ID | Milestone                          | Status        | Primary modules                         |
|----|------------------------------------|---------------|-----------------------------------------|
| M0 | Project setup & data understanding | ✅ Done        | (docs, data exploration)                |
| M1 | Preprocessing pipeline             | ✅ Done        | `imu.py`, `ble.py`, `preprocessing.py`  |
| M2 | Building model & reference data    | ⬜ Next        | `building.py`, `evaluation.py` (loader) |
| M3 | IMU motion model                   | 🟡 Started     | `imu.py`                                |
| M4 | BLE observation model              | ⬜ Planned     | `ble.py`                                |
| M5 | Particle filter (core fusion)      | ⬜ Planned     | `particle_filter.py`                    |
| M6 | Evaluation & experiments           | ⬜ Planned     | `evaluation.py`, `visualization.py`     |
| M7 | Notebook assembly & related work   | ⬜ Planned     | `notebooks/`                            |

Legend: ✅ done · 🟡 partially done · ⬜ not started.

**Dependency order:** M0 → M1 → (M2, M3, M4 can proceed in parallel) → M5 → M6 → M7.
M5 depends on M2, M3, and M4 all being ready.

---

## 2. Detailed milestones

### M0 — Project setup & data understanding ✅

**Objective:** understand the assignment, the data, and the building; set up the
repo skeleton.

- Tasks: read assignment; explore the 4 CSV runs; identify sensor modalities
  (imu accel/gyro/mag/imu_processed, ble_rssi, beacon, live_ble_snapshot);
  review floor maps and the 4 path sketches; read the reference spreadsheet;
  resolve the Run 2 duplicate; write `docs/experiment_protocol.md`.
- **DoD:** protocol document written; data structure understood; beacon layout
  and checkpoint convention documented. **Met.**

---

### M1 — Preprocessing pipeline ✅

**Objective:** turn each raw CSV into clean, time-aligned IMU and BLE streams.

- Modules: `imu.py`, `ble.py`, `preprocessing.py`.
- Output data structure: the `Run` dataclass (`accel`, `gyro`, `mag`,
  `imu_processed`, `ble`, `meta`) with a shared `t_rel` time origin.
- Tasks completed: split by source; clean IMU sub-streams; clean BLE (project
  beacons only, raw RSSI preserved); shared `t0`; metadata + duplicate flag;
  `load_run(run_id)` entry point.
- **DoD:** `load_run` returns a validated `Run` for all four runs; durations
  cross-checked against the reference sheet. **Met.**
- Optional follow-up (deferred): `save_run` / processed-CSV caching if reload
  time becomes annoying.

---

### M2 — Building model & reference data  ⬜ (next)

**Objective:** represent the building for constraints, and load the door
reference timestamps as ground truth.

**Part A — Door reference loader** (`evaluation.py`, loader section)
- Parse `assignment/Paths_references.xlsx` into a tidy table per run:
  `checkpoint_number, floor, room, sum_time_ms, t_rel`.
- Align `sum_time_ms` to the processed timeline; determine the per-run start
  offset (≈0 for Runs 1/3/4; find first-motion offset for Run 2).
- Attach each door reference to a metric (x, y, floor) position (needs Part B).

**Part B — Building geometry** (`building.py`)
- Define a **world coordinate system**: origin, x = east, y = north, plus a
  discrete `floor` index (0 or 1). Align building orientation to world axes
  (assignment requirement).
- Establish a **pixel → metre scale** from the floor plans (use a known room
  width or corridor length as reference).
- Represent the **walkable area** simply: corridor centre-lines / corridor
  polygons per floor (a lightweight polygon or grid mask — keep it simple).
- Place the **door positions** (018–024, 118–124, and the south rooms) as (x, y)
  points along the corridors.
- Place the **8 beacons** (6 known-ish + 2 east-wing TBD) as (x, y, floor).
- Define the **two staircases** as the only allowed floor-transition zones.
- Provide validity checks: `is_walkable(x, y, floor)` and
  `can_change_floor(x, y)`.

- **Inputs:** floor plans, `Paths_references.xlsx`, path descriptions.
- **Outputs:** `building.py` with geometry + validity checks; a reference-point
  table per run with metric positions.
- **DoD:** door references plotted as points on both floor plans in correct
  positions; `is_walkable` returns sensible results along corridors and False
  through walls; beacon positions plotted and consistent with the path sketches.
- **Risks:** hand-drawn maps → approximate coordinates. Mitigation: keep the
  geometry coarse (corridor polygons, not exact walls) and document assumptions.

---

### M3 — IMU motion model  🟡 (started)

**Objective:** convert raw IMU into per-step movement vectors (how far, which
direction) — the motion input to the filter.

- Module: `imu.py`.
- Done: acceleration magnitude; **step detection** (peak-based) → movement-event
  list (`step_id, t_ms, t_rel, magnitude`).
- Remaining tasks:
  1. **Step length**: start with a constant (~0.7 m) or a simple
     Weinberg/Kim style estimate from peak amplitude. Keep it simple first.
  2. **Heading / direction**: estimate travel direction per step. Options
     (simplest first): (a) integrate gyro yaw for relative turns; (b) use the
     magnetometer for absolute heading (noisy indoors); (c) combine. Since the
     phone is in a pocket, expect an unknown constant orientation offset — model
     heading as **relative** and anchor it using the known start direction /
     corridor geometry.
  3. **Motion sector**: turn each step into an "error-prone motion sector" (a
     heading with an angular uncertainty and a step-length uncertainty) — this
     is exactly the motion update the assignment asks for.
- **Inputs:** `Run.accel`, `Run.gyro`, `Run.mag`.
- **Outputs:** a per-step motion table: `t_rel, step_length, heading, heading_sigma`.
- **DoD:** step count is realistic per run (cadence ~1.5–2 Hz); a dead-reckoning
  path built from steps + heading roughly traces the corridor shape (before any
  BLE/map correction). Plots for accel + detected steps and a raw
  dead-reckoning trajectory.
- **Risks:** heading drift and pocket orientation. Mitigation: keep heading
  relative, rely on the particle filter + map to correct absolute drift; validate
  turns against the known path direction changes.

---

### M4 — BLE observation model  ⬜

**Objective:** turn RSSI readings into position evidence, weighting strong
signals more than weak ones (assignment requirement).

- Module: `ble.py`.
- Tasks:
  1. For each BLE reading, map beacon → known (x, y, floor) via `building.py`.
  2. Define an **observation likelihood**: how likely a particle's position is,
     given the observed RSSI from a beacon. Simplest robust approach: model
     "closer beacon ⇒ stronger RSSI" so that a particle near a beacon that
     reports strong RSSI gets a higher weight. Start with a simple monotonic
     RSSI→proximity relation; optionally calibrate a log-distance path-loss model
     if time allows.
  3. **Weight by signal strength:** stronger RSSI contributes more to the update
     (higher confidence); weak/distant beacons contribute little.
  4. Handle **irregular timing / gaps**: BLE is event-driven; the filter updates
     only when a reading arrives.
- **Inputs:** `Run.ble`, beacon positions from `building.py`.
- **Outputs:** a function giving a particle weight from an RSSI observation;
  optionally a smoothed per-beacon RSSI for diagnostics (no smoothing in the
  core stream itself).
- **DoD:** beacon visibility and RSSI-over-time plots per run; a sanity check
  that the strongest beacon at a given time corresponds to the person's location
  from the reference path (e.g. Beacon 4 strong when near room 018).
- **Risks:** RSSI is very noisy and multipath-affected indoors. Mitigation: keep
  the model coarse (proximity, not precise ranging); rely on fusion, not BLE
  alone.

---

### M5 — Particle filter (core fusion)  ⬜

**Objective:** fuse motion + BLE + building constraints into a position estimate
over time. **This is the graded core.**

- Module: `particle_filter.py`.
- Design (kept simple and explainable):
  1. **State per particle:** `(x, y, floor, heading)` (+ weight).
  2. **Initialisation:** sample particles around the known/assumed start
     position (the assignment allows fixing the start point).
  3. **Predict (motion update):** on each detected step, move every particle by
     `step_length` along `heading`, adding Gaussian noise to length and heading
     (the motion sector from M3).
  4. **Constrain (building update):** reject or down-weight particles that land
     in walls / outside corridors; allow floor changes only inside staircase
     zones (`building.py`).
  5. **Update (BLE correction):** when a BLE reading arrives, re-weight particles
     by the M4 observation likelihood (strong RSSI weighted more).
  6. **Resample:** standard resampling when effective sample size drops.
  7. **Estimate:** weighted mean (or best cluster) → estimated position per time.
- **Inputs:** motion table (M3), BLE model (M4), building model (M2).
- **Outputs:** estimated trajectory per run: `t_rel, x, y, floor`.
- **DoD:** the filter runs end-to-end on Run 1 and produces a trajectory that
  stays on the corridors, follows the right floor sequence, and visibly tracks
  the reference path; then runs on all available runs.
- **Risks:** particle depletion, wrong floor transitions, heading divergence.
  Mitigations: enough particles; roughening after resample; tune motion/RSSI
  noise; start simple (2D single floor) then add floor transitions.
- **Suggested sub-steps:** (5a) single-floor PF with motion only → (5b) add
  building constraints → (5c) add BLE update → (5d) add floor transitions.

---

### M6 — Evaluation & experiments  ⬜

**Objective:** measure how good the estimate is, using the door references, and
run the experiments the assignment asks for.

- Modules: `evaluation.py`, `visualization.py`.
- Metrics:
  - **Error at reference points:** distance between the estimated position at
    each door's `t_rel` and the door's true position.
  - **Summary stats:** mean / median / max error per run; aggregate across runs.
  - **Floor accuracy:** fraction of time the estimated floor is correct.
  - **Stability across runs** (assignment guiding question).
- Experiments:
  - Effect of **parameter settings** (particle count, motion/RSSI noise).
  - Effect of **removing a fusion component** (e.g. no map, or no BLE) to show
    each component's contribution — strong material for the discussion.
  - Behaviour at **floor transitions** and in **poor-coverage** areas.
- Visualisations (assignment-listed):
  - Estimated trajectory over the floor plans.
  - Position/time series; error at reference points; parameter comparisons.
- **Inputs:** estimated trajectories (M5), reference table (M2).
- **Outputs:** metric tables and figures per run and overall.
- **DoD:** a reproducible evaluation section with error tables and plots for all
  usable runs, plus at least one ablation/parameter comparison.
- **Note on Run 2:** if its sensor data proves unreliable, evaluate on Runs 1/3/4
  and document the reason (per the protocol).

---

### M7 — Notebook assembly & related work  ⬜

**Objective:** assemble the final, reproducible Jupyter Notebook with all
required sections and the related-work discussion.

- Notebooks to populate: `01_Data_Exploration`, `02_Preprocessing`,
  `03_Step_Detection`, `04_Particle_Filter`, `05_Evaluation`, `Final_Report`.
- Tasks:
  - Each notebook cell has a clear purpose and a short explanation before it
    (per `CLAUDE.md` notebook rules). Notebooks import from `src/`, they do not
    re-implement logic.
  - Assemble `Final_Report.ipynb` covering every required section: setup & data
    collection; experimental protocol; sensors/data sources; preprocessing &
    synchronisation; step detection & motion model; BLE weighting; building
    knowledge; filter modelling & implementation; experimental design &
    evaluation methodology; results; error/limitation discussion; related work.
  - **Related work:** exactly **3 scientific sources** on BLE/IMU/sensor-fusion
    indoor positioning — method, assumptions, and how our approach compares.
- **DoD:** the notebook runs top-to-bottom reproducibly and contains all
  assignment-required sections and the 3-source related-work discussion.

---

## 3. Cross-cutting concerns

- **Coordinate system:** one world frame (x east, y north, `floor` ∈ {0,1});
  defined once in `building.py` and used everywhere. Pixel→metre scale
  documented.
- **Time:** `t_rel` (seconds since run start) is the common clock; `t_ms` kept
  for absolute door alignment.
- **Reproducibility:** fixed random seed for the particle filter; `load_run`
  re-parses raw data deterministically; figures regenerated from code.
- **Testing / validation:** each module validated on **Run 1 first**, then
  generalised to all runs (the pattern we have used so far).
- **Documentation:** keep `docs/experiment_protocol.md`, `docs/decisions.md`
  (method choice, coordinate choices), and `docs/weekly_progress.md` updated as
  we hit each milestone — this feeds the mandatory weekly presentations.

---

## 4. Mapping to assignment deliverables

| Assignment requirement                        | Delivered in |
|-----------------------------------------------|--------------|
| Four documented runs + protocol               | M0, `experiment_protocol.md` |
| Preprocessing & synchronisation               | M1           |
| BLE & IMU quality analysis                    | M1, M3, M4   |
| Step detection from raw acceleration          | M3           |
| Movement direction / motion sector            | M3           |
| BLE weighting by signal strength              | M4           |
| Building structure & constraints              | M2, used in M5 |
| One filtering method (particle filter)        | M5           |
| Evaluation with door references + metrics     | M6           |
| Visualisations (trajectories, errors, params) | M6           |
| Related work (3 sources)                       | M7           |
| Reproducible Jupyter Notebook                 | M7           |

---

## 5. Risks & mitigations (summary)

| Risk                                   | Mitigation                                              |
|----------------------------------------|---------------------------------------------------------|
| Hand-drawn map → imprecise geometry    | Coarse corridor polygons; document assumptions          |
| Heading drift (pocket phone)           | Relative heading + map/BLE correction in the filter     |
| Noisy RSSI / multipath                 | Coarse proximity model; rely on fusion, not BLE alone   |
| Run 2 data reliability                 | Verify start offset; fall back to Runs 1/3/4 if needed  |
| Particle depletion / wrong floor       | Enough particles, roughening, staircase-gated floor change |
| Scope creep                            | One method, coarse models first, refine only if time    |

---

## 6. Suggested schedule (deadline 2026-07-22)

Rough guide, ~2.5 weeks remaining from 2026-07-05:

| Dates (2026)     | Focus                                   |
|------------------|------------------------------------------|
| Jul 05 – Jul 08  | M2 (building model + reference loader)   |
| Jul 08 – Jul 11  | M3 (finish motion model) + M4 (BLE model)|
| Jul 11 – Jul 16  | M5 (particle filter, sub-steps 5a–5d)    |
| Jul 16 – Jul 19  | M6 (evaluation & experiments)            |
| Jul 19 – Jul 22  | M7 (notebook assembly + related work)    |

Buffer is intentionally kept for the filter (M5), which is the hardest part.

---

## 7. Immediate next step

Begin **M2**, starting with the **door reference loader** (parse the xlsx into a
clean per-run table) and then the **building geometry / beacon placement**, since
both M4 and M5 depend on having beacon and door positions in world coordinates.
