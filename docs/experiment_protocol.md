# Experimental Protocol — Indoor Navigation Measurement Campaign

This document records how the four measurement runs were collected, the building
and beacon layout they took place in, and the reference (ground-truth) points
used for evaluation. It follows the structure required by Section 7 of the
assignment.

> Items marked **TBD** need to be filled in by the team (persons, hardware, etc.).

---

## 1. Overview

- **Building:** EMI building, two floors (Level 0 = ground floor, Level 1 = the
  floor physically above it).
- **Date of campaign:** 2026-07-13 (all four runs re-recorded the same session,
  ~11:47–12:09). This replaces an earlier session; the current recordings are the
  authoritative dataset.
- **Smartphone position on body:** trouser pocket (as required by the assignment).
- **Number of runs:** 4, all with complete sensor recordings and all unique (no
  duplicates). During this session the number of steps was also **counted by hand**
  at each checkpoint and recorded in the reference — see Section 4.
- **Sensors recorded per run:** BLE beacon RSSI, raw IMU (accelerometer,
  gyroscope, magnetometer), and the app's filtered IMU stream.
- **Participants / roles:** TBD (three team members).
- **Hardware (phone model, Android version, APK version):** TBD.

---

## 2. Building layout and coordinate reference

Both floors share the same elongated, roughly **L-shaped footprint** with one
long main corridor and a short east wing.

- **Level 0 rooms:** `008`, `009a/b`, `010a/b/c`, `011` (south side of the
  corridor); `018`–`024` (north side); `025` and `008` at the west end; east
  wing `012`–`017`.
- **Level 1 rooms:** mirror Level 0 — `108`, `109a/b/c`, `110a/b`, `111`;
  `118`–`124`; `125`/`108` west; east wing `112`–`117`.
- **Staircases (the only floor-transition points):**
  - **Left / west staircase** — near rooms `025`/`008` (Level 0) and
    `125`/`108` (Level 1).
  - **Right / east staircase** — near rooms `012`/`013` (Level 0) and
    `112`/`113` (Level 1).

Floor plans: `assignment/Floormap_0.png` (Level 0) and
`assignment/floormap_1.png` (Level 1).

---

## 3. Beacon infrastructure

Eight BLE beacons are installed across the two floors. Six of them are visible
in the recorded data and appear in the reference sketches as red circles. Their
approximate positions, reconstructed consistently from all four path
descriptions, are:

| Beacon (name in data) | Floor | Approximate location            |
|-----------------------|-------|---------------------------------|
| `arrive_emi8`         | 0     | West end (left staircase)       |
| `arrive_emi4`         | 0     | East end (right staircase)      |
| `arrive_emi10`        | 0     | Middle of the corridor          |
| `arrive_emi1`         | 1     | West end (left staircase)       |
| `arrive_emi3`         | 1     | East end (right staircase)      |
| `arrive_emi2`         | 1     | Middle of the corridor          |

Only these six beacons are marked (in red) on the path sketches and observed in
the data, so the position estimate uses exactly these six. Any further installed
beacons are not marked on the paths and never appear in the recordings, so they
are omitted.

Metric coordinates for these beacons are defined in `src/building.py`. The metric
scale is **derived from the reference data** (not a guess): the counted step totals
times the measured 0.65 m step length give a real door-to-door spacing of ~5.25 m
(see Section 4 and decision D4).

---

## 4. Reference checkpoints (ground truth)

Ground-truth reference points are the **laboratory doors** along the main
corridors. During each run the person stopped briefly at selected doors; the
timestamps **and the counted step total** were recorded in
`assignment/Paths_references.xlsx`.

**Spreadsheet format** (one block of columns per path):

| Column          | Meaning                                             |
|-----------------|-----------------------------------------------------|
| `Number`        | Checkpoint index (0 = START, last = END)            |
| `Time (ms)`     | Time elapsed since the previous checkpoint           |
| `Sum_Time (ms)` | Cumulative time since the start of the run           |
| `Door`          | `"<floor> <room>"`, e.g. `0 24` = Level 0 / 024      |
| `Step`          | **Counted** cumulative number of steps to this point |

The **`Step`** column is a genuine hand count (not derived from time × pace as in
an earlier version), which makes it strong ground truth for calibrating the step
detector (decision D13) and the building scale (D4). A measured **step length of
65 cm** was established earlier and is kept as `evaluation.STEP_LENGTH_M`.

**Checkpoint convention:** reference checkpoints are logged at the **main
north-corridor doors** — `018`–`024` on Level 0 and `118`–`124` on Level 1 (plus
the extra `121a` on Level 1). The spreadsheet door labels are authoritative for the
reference positions.

For evaluation, `Sum_Time (ms)` is aligned to the processed sensor timeline
(`t_rel`) with `start_offset_s = 0` (the recording clock starts at the START
checkpoint). See Section 5 for the small end-of-run alignment differences.

---

## 5. Data files and quality notes

| Run | File                     | Recording window (local) | Sensor duration | Reference END | Diff     | Counted steps |
|-----|--------------------------|--------------------------|-----------------|---------------|----------|---------------|
| 1   | `Record_data_path_1.csv` | 11:47:56 → 11:50:35      | 158.9 s         | 158.9 s       | +0.03 s  | 216           |
| 2   | `Record_data_path_2.csv` | 11:54:03 → 11:56:58      | 174.9 s         | 179.6 s       | −4.62 s  | 238           |
| 3   | `Record_data_path_3.csv` | 11:58:57 → 12:03:05      | 248.1 s         | 249.5 s       | −1.38 s  | 340           |
| 4   | `Record_data_path_4.csv` | 12:05:16 → 12:08:57      | 206.4 s         | 207.1 s       | −0.63 s  | 282           |

Known issues and anomalies:

- **End-of-run alignment:** for Runs 2–4 the reference END is logged slightly
  *after* the sensor recording stops (Run 2 by ~4.6 s, Runs 3–4 by <1.4 s). The
  final checkpoint(s) can therefore fall just past the end of the sensor data; all
  earlier checkpoints are inside the window. Run 1 aligns almost exactly (+0.03 s).
  The recording clock still starts with the run, so `start_offset_s = 0`.
- **Step-detection validation:** the automatic step detector matches the counted
  totals within ~1.5% (detected 214 / 231 / 335 / 281 vs counted 216 / 238 / 340 /
  282; see D13).
- **Beacon coverage:** only 6 of 8 beacons are seen (the east-wing pair is not
  covered by these paths). BLE sampling is event-driven and irregular, but the gaps
  in this session are small (largest ≈ 1.1 s).
- **Non-project BLE devices:** the raw scan picks up unrelated BLE devices; these
  are filtered out during preprocessing (only `arrive_emi*` beacons kept).

---

## 6. Measurement run summary table

| Run ID | Date/Time (start) | Objective                                        | Persons/Roles | Hardware | Phone position | Start position           | End position                  | Floor transitions            | Notable events            |
|--------|-------------------|--------------------------------------------------|---------------|----------|----------------|--------------------------|-------------------------------|------------------------------|---------------------------|
| 1      | 2026-07-13 11:47  | Loop over both floors; speed-up on Level 1       | TBD           | TBD      | Trouser pocket | Lvl 0, west staircase    | Lvl 1 west (near start)       | 1 up (east), 1 down (west)   | Faster walking on Level 1 |
| 2      | 2026-07-13 11:54  | Two-floor loop; return along Level 0             | TBD           | TBD      | Trouser pocket | Lvl 0, corridor centre   | Lvl 0, mid-corridor           | 1 up (east), 1 down (west)   | Slow constant speed       |
| 3      | 2026-07-13 11:58  | Two Level-0 traversals; one ascent, one descent  | TBD           | TBD      | Trouser pocket | Lvl 0, east near Beacon 4| Lvl 0, west near Beacon 8     | 1 up (west), 1 down (east)   | Both corridor sides       |
| 4      | 2026-07-13 12:05  | Two Level-1 traversals; speed-up on Level 0      | TBD           | TBD      | Trouser pocket | Lvl 0, west (ascends)    | Lvl 0, east near Beacon 4     | 1 up (west), 1 down (west)   | Faster on Level 0         |

Sketches of the actual traversed paths: `assignment/path_1.jpg` … `path_4.jpg`.

**Filter start conditions (fixed per run).** The assignment permits fixing the
start point. Each run's start position and calibrated initial heading are stored in
`preprocessing.RUN_START`. The start position is approximate (first checkpoint plus
the path description, in the rescaled building); the initial heading is calibrated by
aligning each run's first straight corridor leg to the known corridor axis, which
absorbs the unknown pocket-mounting yaw offset (decision D11). Calibrated headings
for this session: **Run 1 +47°, Run 2 +13°, Run 3 −95°, Run 4 +153°** (0° = east).

---

## 7. Detailed path descriptions

Directions are given along the corridor (east = toward the right/east staircase,
west = toward the left/west staircase). Door sequences below are taken directly
from the reference (`sum_steps` in brackets shows the counted progress).

### Path 1 — Loop over both floors, speed-up on Level 1
- Start on **Level 0** at the **west staircase**.
- Walk **east** on Level 0, doors `024→018` (checkpoints 1→7).
- **Ascend** the **east** staircase to Level 1.
- Walk **west** on Level 1, doors `118→124` (checkpoints 8→15).
- **Descend** the **west** staircase back toward the start → End.
- One ascent (east) and one descent (west); faster on Level 1.

### Path 2 — Two-floor loop, return along Level 0
- Start on **Level 0**, corridor **centre** (near door 021).
- Walk **east** on Level 0, doors `021→018` (checkpoints 1→4).
- **Ascend** the **east** staircase to Level 1.
- Walk **west** on Level 1, doors `118→124` (checkpoints 5→12, including `121a`).
- **Descend** the **west** staircase to Level 0.
- Walk **east** on Level 0, doors `024, 023, 022` (checkpoints 13→15) → End.
- Slow constant speed; one ascent (east), one descent (west).

### Path 3 — Two Level-0 traversals; one ascent, one descent
- Start on **Level 0**, **east** near Beacon 4 (door 018).
- Walk **west** on Level 0, doors `018→024` (checkpoints 1→7).
- **Ascend** the **west** staircase to Level 1.
- Walk **east** on Level 1, doors `124→118` (checkpoints 8→15, including `121a`).
- **Descend** the **east** staircase to Level 0.
- Walk **west** on Level 0 again, doors `018→024` (checkpoints 16→22) → End.
- Two full Level-0 traversals; one ascent (west), one descent (east).

### Path 4 — Two Level-1 traversals, speed-up on Level 0
- Start on **Level 0**, **west**; **ascend** the **west** staircase to Level 1
  before the first checkpoint.
- Walk **west→east** on Level 1, doors `124→118` (checkpoints 1→8, including `121a`).
- Walk **east→west** on Level 1, doors `118→124` (checkpoints 9→16).
- **Descend** the **west** staircase to Level 0.
- Walk **west→east** on Level 0 (**faster**), doors `024→018` (checkpoints 17→23)
  → End near Beacon 4.
- One ascent and one descent (both west staircase); faster on Level 0.

---

## 8. Open items

- Fill in **persons/roles** and **hardware** details (Sections 1 and 6).
- **Building scale — resolved:** derived from the counted step totals (~5.25 m door
  spacing) in `src/building.py`; still approximate but reference-based (D4).
- **Start conditions — resolved:** positions + calibrated headings in
  `preprocessing.RUN_START` for this session (D11).
- **End-of-run alignment:** the reference END trails the sensor recording by up to
  ~4.6 s (Run 2); confirm whether the final checkpoint should be dropped from that
  run's evaluation or the recording extended in a future session.
