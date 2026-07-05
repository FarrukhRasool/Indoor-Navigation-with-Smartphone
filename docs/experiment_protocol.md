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
- **Date of campaign:** 2026-06-22 (all four runs recorded the same morning).
- **Smartphone position on body:** trouser pocket (as required by the assignment).
- **Number of runs:** 4 planned. Runs 1, 3, 4 have complete sensor recordings.
  Run 2's original recording was initially lost (a duplicate of Run 1) and was
  later replaced with the correct file — see Section 5.
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

Approximate metric coordinates for these beacons (west/middle/east on each floor)
are defined in `src/building.py`. The scale is nominal (derived from an assumed
door spacing, since no exact building dimensions were available) and can be
adjusted via the constants at the top of that file.

---

## 4. Reference checkpoints (ground truth)

Ground-truth reference points are the **laboratory doors** along the main
corridors. During each run the person stopped briefly at selected doors; the
timestamps were recorded in `assignment/Paths_references.xlsx`.

**Spreadsheet format** (one block of columns per path):

| Column          | Meaning                                        |
|-----------------|------------------------------------------------|
| `Number`        | Checkpoint index (0 = START, last = END)       |
| `Time (ms)`     | Time elapsed since the previous checkpoint      |
| `Sum_Time (ms)` | Cumulative time since the start of the run      |
| `Door`          | `"<floor> <room>"`, e.g. `0 24` = Level 0 / 024 |

**Checkpoint convention (important):** reference checkpoints are always logged
at the **main north-corridor doors** — `018`–`024` on Level 0 and `118`–`124`
on Level 1. When a description says a segment was walked "near rooms 009a–011"
or "near rooms 109a–111", this refers to which **side of the hallway** the
person physically walked, not the door where the checkpoint was recorded. The
spreadsheet door labels are authoritative for the reference positions.

For evaluation, `Sum_Time (ms)` is aligned to the processed sensor timeline
(`t_rel`). For Runs 1, 3, 4 the recording start coincides almost exactly with
the START checkpoint (difference < 0.11 s). Run 2 needs a small start offset —
see Section 5.

---

## 5. Data files and quality notes

| Run | File                        | Recording window (local)      | Sensor duration | Reference END | Difference |
|-----|-----------------------------|-------------------------------|-----------------|---------------|------------|
| 1   | `Record_data_path_1.csv`    | 11:13:44 → 11:17:07           | 197.76 s        | 197.87 s      | −0.11 s    |
| 2   | `Record_data_path_2.csv`    | 11:26:10 → 11:29:27           | 190.48 s        | 182.87 s      | +7.61 s    |
| 3   | `Record_data_path_3.csv`    | 11:35:10 → 11:39:27           | 252.60 s        | 252.64 s      | −0.04 s    |
| 4   | `Record_data_path_4.csv`    | 11:47:04 → 11:50:52           | 227.85 s        | 227.86 s      | −0.01 s    |

Known issues and anomalies:

- **Run 2 duplicate (resolved):** the originally submitted `Record_data_path_2.csv`
  was byte-for-byte identical to Run 1. It was replaced with the correct Run 2
  recording, which is now unique.
- **Run 2 start offset (resolved):** Run 2's sensor duration is ~7.6 s longer
  than its reference window (182.87 s). Analysis of the accelerometer shows the
  person walks continuously from ~1 s after recording start, with ~10 steps
  occurring *after* the END checkpoint (last step at 189.79 s). The extra time is
  therefore **trailing motion after END, not idle time at the start**. The
  recording clock aligns with the reference clock, so **`start_offset_s = 0`**
  for Run 2 (same as Runs 1, 3, 4). The trailing motion falls outside the
  reference window and does not affect evaluation.
- **Beacon coverage:** only 6 of 8 beacons are seen (the east-wing pair is not
  covered by these paths). BLE sampling is event-driven and irregular, with
  occasional gaps (e.g. Run 1's largest BLE gap ≈ 3.8 s).
- **Non-project BLE devices:** the raw scan picks up unrelated BLE devices;
  these are filtered out during preprocessing (only `arrive_emi*` beacons kept).

---

## 6. Measurement run summary table

| Run ID | Date/Time (start) | Objective                                        | Persons/Roles | Hardware | Phone position | Start position                | End position                  | Floor transitions        | Notable events                          |
|--------|-------------------|--------------------------------------------------|---------------|----------|----------------|-------------------------------|-------------------------------|--------------------------|-----------------------------------------|
| 1      | 2026-06-22 11:13  | Closed loop over both floors; speed-up on Lvl 1  | TBD           | TBD      | Trouser pocket | Lvl 0, left staircase         | Same as start (closed loop)   | 1 up (right), 1 down (left) | Faster walking on Level 1               |
| 2      | 2026-06-22 11:26  | Two-floor loop with extra in-place motion        | TBD           | TBD      | Trouser pocket | Lvl 0, corridor centre (021/022) | Same as start (closed loop)   | 1 up (right), 1 down (left) | Loop near Beacon 3; zigzag near Beacon 1 |
| 3      | 2026-06-22 11:35  | Repeated traversals; two ascents, one descent    | TBD           | TBD      | Trouser pocket | Lvl 0, east near Beacon 4     | Lvl 1, west near Beacon 1     | 2 up (left), 1 down (right) | Loop near Beacon 4; both corridor sides |
| 4      | 2026-06-22 11:47  | Two Level-1 traversals; speed-up on Lvl 0        | TBD           | TBD      | Trouser pocket | Lvl 0, west near Beacon 8     | Lvl 0, east near Beacon 4     | 1 up (left), 1 down (left)  | Loop near Beacon 3; faster on Level 0   |

Sketches of the actual traversed paths: `assignment/path_1.jpg` … `path_4.jpg`.

---

## 7. Detailed path descriptions

Directions are given along the corridor (east = toward the right/east staircase,
west = toward the left/west staircase). Checkpoint numbers are the blue markers
in the sketches and match the spreadsheet.

### Path 1 — Closed loop, speed-up on Level 1
- Start = End on **Level 0**, at the **left staircase**.
- Walk **east** on Level 0, checkpoints **1→7** at doors `024→018`.
- **Ascend** the **right** staircase to Level 1.
- Walk **west** on Level 1, checkpoints **8→15** at doors `118→124`.
- **Descend** the **left** staircase back to Level 0 → End (same as start).
- Clockwise loop; one ascent (right) and one descent (left); faster on Level 1.

### Path 2 — Closed loop with loop + zigzag
- Start = End on **Level 0**, corridor **centre** (between rooms 021 and 022).
- Walk **east** on Level 0, checkpoints **1→4** at doors `021, 020, 019, 018`.
- **Ascend** the **right** staircase to Level 1 (near Beacon 3); small **loop**
  near Beacon 3 before entering the corridor.
- Walk **west** on Level 1, checkpoints **5→12** at doors
  `118, 119, 120, 121, 121a, 122, 123, 124`, weaving between corridor sides.
- **Zigzag** near Beacon 1 (west), then **descend** the **left** staircase.
- Walk **east** on Level 0, checkpoints **13→15** at doors `024, 023, 022` → End.
- Slow constant speed throughout; one ascent (right), one descent (left).

### Path 3 — Two ascents, one descent, ends on Level 1
- Start on **Level 0**, **east** near Beacon 4 (room 018); small **loop** near
  Beacon 4 first.
- Walk **west** on Level 0 (north side), checkpoints **1→7** at doors `018→024`.
- **Ascend** the **left** staircase to Level 1 (1st ascent), near Beacon 1.
- Walk **east** on Level 1, checkpoints **8→15** at doors `124→118`.
- **Descend** the **right** staircase (near Beacon 3) to Level 0.
- Walk **west** on Level 0 again (south side), checkpoints **16→22**
  (logged at north doors `018→024`).
- **Ascend** the **left** staircase to Level 1 (2nd ascent); stop near Beacon 1
  → End.
- Two full Level-0 traversals on opposite sides; slow constant speed.

### Path 4 — Two Level-1 traversals, speed-up on Level 0
- Start on **Level 0**, **west** near Beacon 8; **immediately ascend** the
  **left** staircase to Level 1 (no Level-0 walking first).
- Walk **west→east** on Level 1 (south side, near 109a–111), checkpoints **1→8**
  at doors `124→118`.
- **Loop** near Beacon 3 (right staircase area, same floor).
- Walk **east→west** on Level 1 (north side, near 118–124), checkpoints **9→16**
  at doors `118→124`.
- **Descend** the **left** staircase to Level 0.
- Walk **west→east** on Level 0 (**faster**), checkpoints **17→23** at doors
  `024→018` → End near Beacon 4.
- One ascent and one descent (both left staircase); slower on Level 1, faster on
  Level 0.

---

## 8. Open items

- Fill in **persons/roles** and **hardware** details (Sections 1 and 6).
- ~~Determine exact beacon coordinates~~ **Resolved (approximate):** 6 beacons +
  door positions defined in `src/building.py`; scale is nominal and adjustable.
- ~~Confirm the Run 2 start offset~~ **Resolved:** `start_offset_s = 0` (Section 5).
- Reconcile minor **checkpoint-numbering** differences between some path
  descriptions and the spreadsheet (e.g. Path 2 labels the final three
  checkpoints 13–15 while the spreadsheet uses 13, 15, 16).
- Minor spreadsheet typo: Path 3's title cell reads `252640 ms`, but the actual
  cumulative END time (and `04:12,46`) is `252460 ms`. The loader correctly uses
  the real cumulative value (252.46 s).
