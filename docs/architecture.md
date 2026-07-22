# Architecture — Indoor Navigation System

This document describes how the code is organised: the modules, what each is
responsible for, the data structures that flow between them, and the overall
pipeline. It is the technical companion to `docs/implementation_plan.md`.

The design goal is a **simple, modular, readable** system where each file in
`src/` has one clear responsibility, and the notebooks only orchestrate and
present — they never re-implement logic.

Legend: ✅ implemented · 🟡 partially implemented · ⬜ planned.

---

## 1. Architectural overview

The system is organised as a **layered pipeline**. Data flows from raw files at
the bottom up to the final position estimate and evaluation at the top.

```
                        ┌───────────────────────────────┐
   Presentation layer   │  notebooks/  +  visualization  │   plots, tables, report
                        └───────────────┬───────────────┘
                                        │
                        ┌───────────────┴───────────────┐
   Estimation layer     │        particle_filter.py      │   fuse everything → trajectory
                        └───┬───────────┬───────────┬────┘
                            │           │           │
              ┌─────────────┘     ┌─────┘     └─────────────┐
   Model      │  imu.py       │   │  ble.py       │   │  building.py    │
   layer      │  (motion)     │   │  (observation)│   │  (constraints)  │
              └──────┬────────┘   └──────┬────────┘   └───────┬─────────┘
                     │                   │                    │
                     └─────────┬─────────┘                    │
                               │                              │
   Data layer        ┌─────────┴──────────┐        ┌──────────┴─────────┐
                     │  preprocessing.py  │        │  evaluation.py     │
                     │  (Run objects)     │        │  (reference loader)│
                     └─────────┬──────────┘        └──────────┬─────────┘
                               │                              │
   Raw inputs        ┌─────────┴──────────────────────────────┴─────────┐
                     │ data/raw/*.csv   assignment/Paths_references.xlsx │
                     │ assignment/Floormap_0.png, floormap_1.png         │
                     └───────────────────────────────────────────────────┘
```

- **Data layer** loads and cleans everything into well-defined structures.
- **Model layer** turns clean data into the three fusion ingredients: motion
  (IMU), observations (BLE), constraints (building).
- **Estimation layer** is the particle filter that fuses those three.
- **Presentation layer** evaluates and visualises the result.

---

## 2. Repository structure

```
Embedded Intelligence Final Assignment/
├── assignment/            # given material: assignment text, floor maps,
│                          #   path sketches, Paths_references.xlsx
├── data/
│   ├── raw/               # the four Record_data_path_*.csv recordings
│   ├── processed/         # (optional) cached cleaned streams
│   └── runs/              # (optional) saved filter outputs
├── docs/                  # requirements, architecture, plan, protocol, decisions
├── figures/              # generated plots (regenerable, not source of truth)
├── notebooks/            # 01..05 + Final_Report (orchestration + presentation)
└── src/                  # all logic lives here, one responsibility per file
    ├── imu.py
    ├── ble.py
    ├── preprocessing.py
    ├── building.py
    ├── particle_filter.py
    ├── evaluation.py
    └── visualization.py
```

---

## 3. Module reference

Each module below lists its **responsibility**, **key functions** (current and
planned), **inputs/outputs**, **dependencies**, and an explicit **does NOT**
list to keep responsibilities from leaking across files.

### 3.1 `preprocessing.py` — data orchestrator ✅

- **Responsibility:** the single entry point that loads a raw CSV, splits it by
  source, delegates cleaning to `imu.py` and `ble.py`, assigns one shared time
  origin, collects metadata, and returns a `Run` object.
- **Key functions:**
  - `load_run(run_id, raw_dir) -> Run` — the main entry point for notebooks.
  - `run_file_path`, `hash_file`, `find_duplicate_runs` — file handling and
    duplicate detection (Run 1/Run 2 history).
  - `build_metadata(...)` — descriptive stats only (never mutates data).
- **Inputs:** `data/raw/Record_data_path_{id}.csv`.
- **Outputs:** a `Run` dataclass (see §4.1).
- **Depends on:** `imu.py`, `ble.py`, pandas.
- **Does NOT:** detect steps, model BLE, filter, or plot.

### 3.2 `imu.py` — IMU loading + motion model ✅

- **Responsibility:** clean IMU sub-streams and derive motion (steps → movement
  vectors).
- **Key functions:**
  - `extract_imu_stream`, `extract_all_imu_streams` — build clean
    accel/gyro/mag/imu_processed DataFrames. ✅
  - `acceleration_magnitude(accel)` — orientation-free magnitude. ✅
  - `detect_steps(accel, ...)` — peak-based step events. ✅
  - `heading_from_gyro(gyro, ...)` — gyro-integrated relative heading. ✅
  - `build_motion_table(run, ...)` — the per-step motion table (§4.2). ✅
- **Inputs:** IMU rows (from `preprocessing.py`), or a `Run`.
- **Outputs:** clean IMU streams; movement-event list; motion table.
- **Depends on:** numpy, pandas, scipy.signal.
- **Does NOT:** touch BLE, building, or filtering logic.

### 3.3 `ble.py` — BLE loading + observation model ✅

- **Responsibility:** clean BLE readings and turn RSSI into position evidence.
- **Key functions:**
  - `is_project_beacon`, `extract_ble_stream` — keep project beacons, raw RSSI,
    shared `t_rel`. ✅
  - `expected_rssi(distance)` — log-distance path-loss expected RSSI. ✅
  - `rssi_likelihood(particle_x, particle_y, particle_floor, beacon_position,
    observed_rssi)` — weight particles by how well their position explains the
    observed RSSI (Gaussian on the RSSI residual), stronger RSSI weighted more,
    soft floor-mismatch penalty. Vectorised over particles. ✅
- **Inputs:** `ble_rssi` rows (from `preprocessing.py`); the observed beacon's
  `(x, y, floor)` position, passed in by the caller (from `building.py`).
- **Outputs:** clean BLE stream; per-particle weights for one RSSI reading.
- **Depends on:** numpy, pandas. (Beacon positions are passed in, so `ble.py`
  does not import `building.py`.)
- **Does NOT:** process IMU, run the filter, or plot.

### 3.4 `building.py` — building model & constraints ✅

- **Responsibility:** represent the two-floor building geometry and enforce
  movement constraints.
- **Key functions:**
  - `corridor_polyline(floor) -> list` — the corridor centre-line as a list of
    connected `(x, y)` points (main corridor + east stub). ✅
  - `distance_to_corridor(x, y, floor) -> float` — shortest distance from a point
    to the corridor centre-line (uses the `_distance_point_to_segment` helper). ✅
  - `is_walkable(x, y, floor) -> bool` — within `CORRIDOR_HALF_WIDTH_M` of the
    corridor. ✅
  - `can_change_floor(x, y) -> bool` — inside a staircase zone (within
    `STAIRCASE_RADIUS_M` of the west or east staircase). ✅
  - `door_positions() -> dict` — `(floor, room)` → `(x, y, floor)`. ✅
  - `beacon_positions() -> dict` — beacon name → `(x, y, floor)` for the six
    observed beacons. ✅
- **Geometry source:** the layout is fixed by module-level constants
  (`DOOR_SPACING_M`, `MAIN_CORRIDOR_LENGTH_M`, `WEST_OFFSET_M`, …). The metric
  scale is derived from the counted step totals (decision D4), not from a
  pixel→metre conversion — there is no `pixel_to_world`.
- **Inputs:** none at runtime; geometry is hard-coded constants derived from the
  maps and the reference step counts.
- **Outputs:** geometry queries used by the filter and evaluation.
- **Depends on:** the standard-library `math` module only.
- **Does NOT:** load sensor data, filter, or plot.

### 3.5 `particle_filter.py` — core fusion ✅

- **Responsibility:** estimate position over time by fusing motion + BLE +
  building constraints. This is the graded core.
- **Key functions:**
  - `initialise_particles(start, n_particles, rng, spread)` — sample a cloud
    around the known start position. ✅
  - `predict(x, y, step, rng, length_sigma)` — motion update: move every particle
    by one step of the motion table (with length/heading noise). ✅
  - `constraint_weights(x, y, floor, building, wall_sigma)` — soft-wall weight per
    particle from `building.distance_to_corridor` (the building update). ✅
  - `effective_sample_size(weights)`, `systematic_resample_indices(weights, rng)`,
    `resample(x, y, weights, rng)` — the resampling machinery (resample when ESS
    drops). ✅
  - `maybe_change_floor(x, y, floor, building, rng, p)` — staircase-gated
    stochastic floor flips. ✅
  - `estimate(x, y)` (mean position), `estimate_floor(floor, weights)` (weighted
    majority floor), `cloud_spread(x, y)` (RMS spread diagnostic). ✅
  - Staged runners, each returning an estimated trajectory:
    `run_motion_only` (5a), `run_with_constraints` (5b, + map),
    `run_with_ble` (5c, + RSSI weighting), `run_filter` (5d, the full filter with
    floor transitions). ✅
- **Inputs:** motion table (`imu.py`), the cleaned BLE stream and `ble` model,
  the `building` module — all **passed in as arguments** to the runners.
- **Outputs:** estimated trajectory (§4.4).
- **Depends on:** numpy, pandas. The `building` and `ble` modules are **passed in
  as arguments** (not imported), which keeps the filter decoupled from geometry
  and the observation model.
- **Does NOT:** load/parse data or plot.

### 3.6 `evaluation.py` — reference data + metrics ✅

- **Responsibility:** load the door reference ground truth and compute error
  metrics against the estimated trajectory.
- **Key functions:**
  - `load_reference(run_id, reference_file, start_offset_s) -> DataFrame` — parse
    `Paths_references.xlsx` into a tidy per-run table (§4.3), aligned to `t_rel`
    and with each door's `(x, y)` attached from `building.door_positions`. Uses
    the `parse_door` and `find_header_row` helpers. ✅
  - `error_at_references(trajectory, reference) -> DataFrame` — per-checkpoint
    position error (estimate interpolated to each checkpoint time) plus whether
    the estimated floor is correct. The door positions already live in the
    reference table, so `building` is not needed here. ✅
  - `summary_metrics(per_checkpoint) -> dict` — mean/median/max error, floor
    accuracy, and checkpoint count. ✅
  - `compare_metrics(named_trajectories, reference) -> DataFrame` — one
    `summary_metrics` row per named variant (the fusion ablation). ✅
- **Inputs:** `Paths_references.xlsx`, an estimated trajectory (passed in).
- **Outputs:** reference table; per-checkpoint and summary metric tables.
- **Depends on:** pandas (openpyxl engine for the xlsx), numpy, `building.py`.
- **Does NOT:** run the filter or draw plots (delegates drawing to
  `visualization.py`).

### 3.7 `visualization.py` — plotting only ✅

- **Responsibility:** all plotting. Takes already-prepared data and draws it.
- **Key functions:**
  - IMU / step diagnostics: `plot_acceleration_with_steps`, `plot_heading`,
    `plot_dead_reckoning`, `plot_step_count_comparison`. ✅
  - Filter trajectories: `plot_particle_cloud`, `plot_trajectory_on_corridor`,
    `plot_trajectory_two_floors`, `plot_floor_over_time`. ✅
  - Evaluation: `plot_error_at_references` (one bar per door checkpoint, coloured
    by floor correctness), `plot_ablation` (map-only / +BLE / full comparison). ✅
- **Depends on:** matplotlib, numpy, and `imu.py` (for
  `plot_acceleration_with_steps`); reads `Run` / trajectory / metric structures.
- **Does NOT:** compute anything (no filtering, preprocessing, or metrics).

---

## 4. Core data structures (contracts)

These structures are the "contracts" between layers. Keeping them stable lets
modules evolve independently.

### 4.1 `Run` (in `preprocessing.py`) ✅

```
Run
 ├─ run_id: int
 ├─ t0_ms: int                 # shared time origin
 ├─ duration_s: float
 ├─ accel, gyro, mag: DataFrame # columns: t_ms, t_rel, x, y, z
 ├─ imu_processed: DataFrame    # app-filtered IMU (comparison only)
 ├─ ble: DataFrame              # columns: t_ms, t_rel, beacon, address, rssi
 └─ meta: dict                  # counts, dropped rows, beacon stats, flags
```

### 4.2 Motion table (from `imu.py`) ✅

One row per detected step:

| column        | meaning                                  |
|---------------|------------------------------------------|
| `t_rel`       | time of the step (s since run start)     |
| `step_length` | estimated step length (m)                |
| `heading`     | estimated travel direction (rad, world)  |
| `heading_sigma` | angular uncertainty of the motion sector |

### 4.3 Reference table (from `evaluation.py`) ✅

One row per door checkpoint:

| column        | meaning                                   |
|---------------|-------------------------------------------|
| `number`      | checkpoint index (0 = START)              |
| `floor`       | 0 or 1                                     |
| `room`        | e.g. `024`, `121a`                        |
| `sum_time_ms` | cumulative time from run start            |
| `t_rel`       | aligned time on the processed timeline     |
| `x`, `y`      | metric position of the door (from building)|

### 4.4 Estimated trajectory (from `particle_filter.py`) ✅

| column | meaning                          |
|--------|----------------------------------|
| `t_rel`| time (s since run start)         |
| `x`, `y` | estimated position (m)         |
| `floor`| estimated floor (0 or 1)         |

### 4.5 Particle state (internal to `particle_filter.py`) ✅

Each particle: `(x, y, floor, heading, weight)`. Represented compactly (e.g.
numpy arrays) for speed; never leaks outside the filter.

---

## 5. End-to-end data flow

For one run:

1. **`load_run(id)`** → `Run` (clean IMU + BLE, shared `t_rel`, metadata).
2. **`imu.build_motion_table(run)`** → motion table (steps with length + heading).
3. **`building`** provides beacon/door positions and validity checks.
4. **`evaluation.load_reference(id)`** → reference table (door truth on `t_rel`).
5. **`particle_filter.run_filter(run, motion_table, building, ble_model)`**:
   - walk the shared timeline;
   - **predict** on each step (motion), **constrain** via `building`;
   - **update** on each BLE reading (RSSI weighting), **resample** as needed;
   - emit the **estimated trajectory**.
6. **`evaluation`** compares trajectory vs reference → error metrics.
7. **`visualization`** draws trajectory-on-map, RSSI, and error plots.
8. **Notebooks** orchestrate steps 1–7 and present the results.

BLE is **event-driven**: the filter predicts continuously from steps and only
performs a measurement update when a BLE reading actually arrives (no forced
resampling of BLE onto a fixed grid).

---

## 6. Coordinate system & conventions

- **World frame:** x = east, y = north, metric (metres). A single origin is
  defined in `building.py` and shared everywhere.
- **Floors:** discrete `floor ∈ {0, 1}`; floor 0 is physically the lower/ground
  floor, floor 1 is above it.
- **Floor transitions:** allowed only inside the two staircase zones (west and
  east ends), enforced by `building.can_change_floor`.
- **Time:** `t_rel` (seconds since run start) is the common clock across all
  streams; `t_ms` (absolute) is retained for aligning the door references.
- **Headings:** radians in the world frame; because the phone is pocket-carried,
  heading is treated as **relative** and anchored using the known start
  direction and corridor geometry.
- **Metric scale:** documented once in `building.py` via the `DOOR_SPACING_M`
  constant, derived from the counted step totals in the reference (decision D4),
  not from a pixel→metre conversion of the floor plans.

---

## 7. Module dependency graph

```
notebooks ─────────────► (everything, for orchestration)

visualization ─► matplotlib, numpy, imu (for the step-plot helper)
particle_filter ─► numpy, pandas   (building + ble passed in as arguments)
evaluation ─────► numpy, pandas, building   (pandas uses openpyxl for the xlsx)
imu ────────────► numpy, pandas, scipy.signal
ble ────────────► numpy, pandas   (beacon positions passed in, no building import)
building ───────► math (standard library)
preprocessing ──► imu, ble, pandas
```

Rules:
- Lower layers never import higher layers (no `imu` importing `particle_filter`).
- `visualization` and notebooks are the only places allowed to depend broadly.
- `building` is a leaf dependency (geometry only). It is imported directly only
  by `evaluation`; the filter and `ble` receive geometry/positions as arguments
  instead, which keeps them decoupled.

---

## 8. Notebook layer

Notebooks are **thin orchestration + narrative**. They import from `src/`,
call functions, and present results. Per `CLAUDE.md`, each cell has one purpose
with a short explanation before it.

| Notebook                 | Purpose                                        |
|--------------------------|------------------------------------------------|
| `01_Data_Exploration`    | raw data structure, sensor overview, quality   |
| `02_Preprocessing`       | `load_run`, cleaned streams, synchronisation   |
| `03_Step_Detection`      | step detection + motion model                  |
| `04_Particle_Filter`     | the filter, trajectories on the map            |
| `05_Evaluation`          | metrics, error plots, experiments              |
| `Final_Report`           | the complete, submission-ready write-up        |

---

## 9. Design principles

- **Single responsibility per module** — enforced by the "does NOT" lists above.
- **Stable data contracts** — modules talk through the structures in §4, not
  through each other's internals.
- **Validate on Run 1 first**, then generalise to all runs.
- **Simplest correct version first** — coarse models (constant step length,
  proximity RSSI, corridor polygons) before any refinement.
- **Reproducibility** — deterministic loading; fixed random seed in the filter;
  figures regenerated from code, not stored as the source of truth.
- **No premature abstraction** — no classes/frameworks beyond the small `Run`
  (and the particle arrays inside the filter).

---

## 10. Where future logic goes (extension points)

| If we need to…                          | Put it in…                        |
|-----------------------------------------|-----------------------------------|
| Improve step length / heading            | `imu.py` (motion model)           |
| Calibrate a path-loss RSSI model         | `ble.py` (observation model)      |
| Refine walls / add rooms / east wing     | `building.py`                     |
| Change filter behaviour or tuning        | `particle_filter.py`              |
| Add a new metric or experiment           | `evaluation.py`                   |
| Add a new plot                           | `visualization.py`                |

This keeps every change localised to one module and easy to explain in class.
