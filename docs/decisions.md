# Design Decisions (Decision Log)

Short records of the important choices we made and why. Newest at the bottom.

---

## D1 — Filtering method: Particle Filter

**Decision:** Use a **Particle Filter** as the single filtering method (not a
Kalman filter).

**Why:**
- The problem is a person constrained to narrow corridors on two floors, with
  hard building constraints (walls, staircases) and noisy, multi-modal RSSI.
- A particle filter handles these naturally: invalid positions can simply be
  rejected or down-weighted, and multiple position hypotheses can be kept at
  once. The assignment itself notes this is easier than in a Kalman filter.
- Our runs are short (3–4 min) and processed offline, so the extra compute of
  many particles is not a concern.

**Status:** Confirmed.

---

## D2 — Coordinate system

**Decision:** One world frame: origin at the west staircase on floor 0,
x = east, y = north, units in metres, with a separate discrete `floor` index
(0 = lower/ground, 1 = upper). Both floors share the same 2-D footprint.

**Why:** Simple, matches the corridor orientation, and lets floor changes be a
discrete event gated to staircases. Defined once in `building.py`.

---

## D3 — Building geometry: centre-line + half-width

**Decision:** Model each floor's walkable space as a centre-line poly-line (main
corridor + short east stub) with a half-width, rather than exact wall polygons
or an image-based occupancy grid.

**Why:** Simplest model that is still faithful for a corridor building; easy to
explain and to query (`is_walkable` = distance-to-line ≤ half-width).

---

## D4 — Metric scale derived from the reference (door spacing ~5.25 m)

**Decision:** Set the building's metric scale from the reference data rather than a
guess. Multiplying the **counted** step totals in `Paths_references.xlsx` by the
measured 0.65 m step length gives the real distances. The four one-way
door-24→door-18 traversals are tightly consistent at **5.09–5.42 m per spacing**
(mean ≈ 5.25 m), and Run 1's START→door-24 (13 steps) implies ~8.5 m from the west
staircase to the first door. So `DOOR_SPACING_M = 5.25`, `WEST_OFFSET_M = 8.5`,
`MAIN_CORRIDOR_LENGTH_M = 44`, `EAST_STUB_LENGTH_M = 6`; doors, beacons, corridor,
and staircases derive from these.

**Why:** The earlier nominal 4.5 m was a guess that made the model too small. With
the counted step totals the estimate is far tighter than the previous
time×pace-derived data (which had ranged 3.8–9.8 m/spacing).

**Caveat:** still approximate (adjacent-segment distances vary with weaving), but
the traversal-averaged 5.25 m is well supported. Rescaling changes the filter's
coordinate scale, so the filter (on the development branch) should be re-evaluated
against it.

---

## D5 — Beacons: the six marked on the paths

**Decision:** Model exactly the six beacons marked in red on the path sketches
(`emi1, 2, 3, 4, 8, 10`), three per floor (west, middle, east).

**Why:** These are the beacons that actually appear in the recordings; any others
are not marked on the paths and never observed, so they cannot help the estimate.

---

## D6 — Heading from gyro projected onto gravity

**Decision:** Estimate travel-direction changes by projecting the gyroscope onto
the vertical (gravity) axis to get the yaw rate, then integrating it. The
vertical is estimated from the mean accelerometer vector (the phone keeps a
roughly constant orientation in the pocket during a run). Step length is a
constant for now; heading is treated as relative and anchored to the known start
direction.

**Why:** Orientation-robust for a pocket-carried phone and simple to implement.
Absolute heading drift is expected and will be corrected later by the particle
filter using the building map and BLE. The magnetometer is avoided as the primary
source because indoor magnetic fields are unreliable.

**Status:** Confirmed (M3).

---

## D7 — BLE observation model: log-distance path-loss likelihood

**Decision:** Turn each RSSI reading into a particle weight with the standard
**log-distance path-loss** model: the expected RSSI at a particle is
`RSSI_AT_1M - 10 · n · log10(distance)`, and the weight is a Gaussian on the
difference between the observed and expected RSSI. A floor mismatch adds a soft
distance penalty rather than a hard zero (staircase signal bleed). Parameters are
nominal constants at the top of `ble.py` and tunable during filter work.

**Why:**
- It is the textbook BLE indoor-positioning model, so it is easy to justify and
  cite in the related-work section.
- "Weight strong signals more" falls out for free: a strong RSSI is only
  explained by particles close to the beacon (very discriminating), while a weak
  RSSI is explained by a large far-away region (barely discriminating).
- Simple to compute in the RSSI domain; no need to invert RSSI into a distance.

**Status:** Confirmed (M4). Sanity check: `arrive_emi4` is the strongest beacon at
door 018 in all runs; strongest-beacon floor accuracy 64–87% and nearest-beacon
match 48–60% (both above the ~33% chance level) — coarse but real, as expected for
BLE, which is why fusion with IMU and the map is needed.

---

## D8 — Particle filter: incremental build, position-only state for 5a

**Decision:** Build the particle filter (M5) in four sub-steps — 5a motion-only,
5b add building constraints, 5c add BLE update + resample, 5d add floor
transitions — instead of all at once. For **5a**, a particle is just its position
`(x, y)` with a uniform weight; on each step every particle draws its own step
length `Normal(step_length, 0.15 m)` and heading `Normal(heading, heading_sigma)`
from the M3 motion table and moves. The point estimate is the cloud mean.

**Why:**
- Incremental sub-steps mean each new piece (map, BLE, floor changes) is added to
  scaffolding already proven to run, which is easier to debug and to explain.
- 5a validates the *predict* half of the filter against a known reference (the M3
  dead-reckoning path) before any correction can mask a bug.
- Persistent per-particle `heading` and `floor` (architecture §4.5) are only
  needed once constraints and floor changes arrive, so they are deferred to the
  later sub-steps to keep 5a minimal.

**Status:** 5a confirmed. The filter mean tracks dead reckoning (mean gap
1.1–2.4 m, growing with step count — the expected contraction from averaging over
heading noise), the cloud spread grows from ~0.7 m to ~3.8–4.4 m, and the result
is deterministic under a fixed seed on all four runs.

---

## D9 — Building constraint: narrow soft wall (5b)

**Decision:** In sub-step 5b, weight each particle by walkability using a soft
wall — `weight = exp(-½·(overshoot / wall_sigma)²)` where
`overshoot = max(0, distance_to_corridor − half_width)` — then resample
(systematic) when the effective sample size drops below half. After a sweep over
all four runs, set **`wall_sigma = 0.1 m`**, which acts as a nearly hard wall.

**Why:**
- A soft formulation avoids the all-zero-weight collapse in principle, and reads
  cleanly (one expression, no special-casing), but the sweep showed that a
  **narrow** wall works best: walkability of the estimate roughly doubled going
  from `wall_sigma = 0.5` to `0.1` (e.g. Run 1: 0.12 → 0.23; four-run mean
  0.08 → 0.12), and kept improving down to ~0.05 with diminishing returns. A wide
  wall keeps off-corridor particles alive and constrains too weakly.
- The narrow value gives strong selective pressure during resampling to keep the
  cloud on the corridor, while a hair of gradient (plus the plain-mean guard when
  every weight underflows to zero) avoids the pathologies of a pure hard cut.

**Honest limitation (important for the evaluation):** the map constraint alone
cannot correct **heading drift**. On the portion of a run where the gyro heading
is still reliable, the constrained estimate tracks the corridor well (Run 1's
first eastward traversal sits inside the corridor band); once heading drift
accumulates, the whole cloud leaves the corridor and the map can only damp the
excursion, not fix the direction. This is exactly the ablation result the
assignment asks for and the motivation for the BLE update in 5c: an **absolute**
reference is needed to correct drift. Walkability stays low on Runs 3/4, which
have the largest accumulated drift.

**Status:** 5b confirmed. `run_with_constraints` takes a tunable `wall_sigma`
(default 0.1); resampling is active, results are deterministic under a fixed seed,
and the estimate is markedly more walkable than 5a on all four runs.

---

## D10 — Step length calibrated to ~0.5 m (motion-model scale fix)

**Decision:** Change the constant step length in `imu.build_motion_table` from the
initial guess **0.70 m to 0.50 m**, calibrated against known corridor legs in the
reference data.

**Why:** While bringing up the BLE filter (5c) the estimated path was far too
long. Measuring a clean, straight, single-floor leg against the door references:

| Run | Leg (floor 0) | Distance | Steps | Implied step length |
|-----|---------------|----------|-------|---------------------|
| 1 | 024→018 | 27.0 m | 67 | 0.40 m |
| 2 | 021→018 | 13.5 m | 13 | 1.04 m (outlier — under-counted steps) |
| 3 | 018→024 | 27.0 m | 53 | 0.51 m |
| 4 | 024→018 | 27.0 m | 51 | 0.53 m |

The reliable runs (1, 3, 4) cluster at 0.40–0.53 m; Run 2 is an outlier (only 13
steps on a short leg). At 0.70 m the Run 1 path was 1.74× too long, which made the
particle cloud overshoot every corridor and beacon. A single calibrated constant
**0.50 m** roughly halved the door-checkpoint error on every run (e.g. Run 1 5b:
13.0 → 3.6 m; Run 4 5b: 97.8 → 19.7 m).

**Choice of a global constant** (not per-run) keeps it simple and avoids `imu.py`
depending on the door references. Per-run stride calibration is a possible later
refinement (the runs may be different walkers).

**Known follow-up:** a second motion-model boundary condition, the per-run
**initial heading**, still defaults to 0 (east) for every run. Runs that do not
start walking east (e.g. Run 3 starts west) launch in the wrong direction; setting
Run 3's initial heading to π cut its early-leg error 19.4 → 11.1 m. This is fixed
next, in the orchestration layer (start position + heading are known, fixable
boundary conditions per the assignment).

**Update (ground truth from the reference).** The reference recorded a measured
**step length of 65 cm (0.65 m)**. We use **0.65 m** as the step length
(`build_motion_table` default), kept as the constant `evaluation.STEP_LENGTH_M` (the
re-recorded workbook no longer stores the cell). The earlier 0.40–0.53 m figures
were an artefact of our nominal building scale being too small; the building has
since been rescaled from the counted step totals (see D4). The step length itself is
a measured value, not a guess.

**Status:** Superseded — step length is **0.65 m** (measured, from the reference).
Still a tunable parameter of `build_motion_table`.

---

## D11 — Per-run initial heading calibrated from corridor geometry

**Decision:** Set the filter's per-run **initial heading** (the absolute direction
the integrated gyro heading is anchored to) by aligning each run's **first straight
corridor leg** to the known corridor axis, rather than leaving it at 0 (east) for
all runs. The calibrated start conditions live in `preprocessing.RUN_START`
(start position + floor + `initial_heading` in radians).

**Why:** The gyro gives only *relative* heading; the absolute anchor depends on how
the phone sat in the pocket, an unknown constant yaw offset that differs per run.
The assignment explicitly expects this and suggests anchoring to the known start
direction / corridor geometry. For the first floor-0 leg (known to run east or
west), the mean gyro heading over the leg is mapped onto that axis; the required
offset is the initial heading. This uses **prior path knowledge and geometry**, not
the door-error metric itself, so it does not overfit the evaluation references.

Calibrated values: Run 1 +32°, Run 2 +10°, Run 3 −132°, Run 4 +147°. Effect on the
map-only (5b) floor-0 door error:

| Run | default 0 | calibrated | note |
|-----|-----------|------------|------|
| 1 | 3.6 m | 3.2 m | clean early leg |
| 2 | 11.5 m | 10.7 m | short, under-counted leg → weak estimate |
| 3 | 17.1 m | 8.8 m | large gain (Run 3 starts walking west) |
| 4 | 19.7 m | 18.8 m | walks floor 0 only at the end → weak anchor |

**Honest limitation:** the calibration only helps where a clean early single-floor
leg exists (Runs 1, 3). Run 2's leg is short and its steps under-counted; Run 4
walks floor 0 only at the very end, after the gyro has drifted through the whole
run, so its anchor is weak. These remain documented weaknesses to be discussed in
the evaluation; the BLE + map fusion is what must ultimately absorb residual
heading error.

**Status:** Confirmed. Values stored in `preprocessing.RUN_START`; the constants
depend only on the (stable) heading-estimation code, not on step length.

---

## D12 — Floor transitions: staircase-gated stochastic flips + BLE selection (5d)

**Decision:** Complete the particle filter (`run_filter`) by giving each particle a
**floor** and letting it switch floor (0↔1), with probability
`FLOOR_CHANGE_PROB = 0.15` per step, **only while inside a staircase zone**
(`building.can_change_floor`). The BLE update then keeps whichever particles are on
the floor whose beacons match the reading. No barometer or explicit stair detection
is used — the filter resolves the floor itself. This is the particle-filter-native
approach the assignment points to (invalid states are simply down-weighted).

**Why this design:** it is simple, reuses the existing predict/weight/resample
machinery (only the floor array and a staircase-gated flip are added), and keeps
floor changes physically constrained to staircases.

**Results (full filter, all reference checkpoints, new recordings):**

| Run | Floor accuracy | Door error (5c 1-floor → 5d) |
|-----|----------------|-------------------------------|
| 1 | 0.47 | 13.4 → 14.5 m |
| 2 | 0.41 | 29.3 → 29.3 m |
| 3 | 0.62 | 18.5 → 17.5 m |
| 4 | 0.64 | 21.7 → 19.8 m |

Floor accuracy averages ~0.53; floor handling changes position error only slightly.

**Honest limitations (evaluation material, M6):**
- **Spurious early flip.** A run that *starts* on a staircase (Run 1, west staircase
  `(0,0)`) flips floor almost immediately (its estimated floor jumps to 1 at ~8 s,
  while the person is on floor 0 until ~45 s).
- **Weak BLE floor discrimination.** The calibrated flat path-loss (n≈1.19, D14)
  means the distance-based `FLOOR_PENALTY_M` produces only a few dB, too small
  against the ~6.5 dB noise to reliably distinguish floors.
- **Position drift starves the floor logic.** When the cloud never reaches a
  staircase zone, no floor-1 hypotheses are created — Run 2 makes **0 flips**.

An attempted "must leave the start staircase before flipping" gate was tried and
**rejected**: it broke runs that legitimately change floor immediately (Run 4
ascends at the start), lowering average floor accuracy. A better future option is
BLE-gated flips (bias toward the currently strongest floor), noted for M6/future
work.

**Status:** Confirmed. M5 complete. Filter is deterministic under a fixed seed and
runs on all four runs; accuracy is realistic for a coarse indoor system, as the
assignment expects.

---

## D13 — Step-detection threshold calibrated to the reference step counts

**Decision:** Set the peak-height threshold in `imu.detect_steps` to
`mean + 1.0 * std` of the acceleration magnitude (the `height_std_factor`
parameter, default 1.0).

**Why:** the re-recorded `Paths_references.xlsx` records a **counted** cumulative
step total per checkpoint (the `Step` column) — actual ground truth, not the earlier
time×pace estimate. Against these counted totals the detected count is stable across
nearby thresholds (the new recordings have clean, well-separated peaks), and
`mean + 1.0 * std` matches to within ~1.5%:

| Run | detected (1.0·std) | reference (counted) | ratio |
|-----|--------------------|---------------------|-------|
| 1 | 214 | 216 | 0.99 |
| 2 | 231 | 238 | 0.97 |
| 3 | 335 | 340 | 0.99 |
| 4 | 281 | 282 | 1.00 |

Mean ratio ≈ 0.99. (An earlier calibration against the *derived* counts used 1.25;
the new counted totals and cleaner recordings put the best value back at 1.0.)

**Why this is not overfitting:** the counted totals are true step counts, so matching
them is a genuine calibration against ground truth.

**Status:** Confirmed. `height_std_factor` remains a tunable parameter of
`detect_steps`.

---

## D14 — BLE path-loss model calibrated to the reference distances

**Decision:** Replace the nominal path-loss parameters in `ble.py` with values fit
to the data: `RSSI_AT_1M = -76.5`, `PATH_LOSS_EXPONENT = 1.19`, `RSSI_SIGMA = 6.5`
(was −59, 2.5, 6.0).

**Why:** When BLE was first added to the filter (5c), it *worsened* the estimate on
the clean run (Run 1 door error 1.96 → 4.44 m). A diagnosis showed the signal was
fine — the strongest-heard beacon matched the geometrically nearest one at 6/7
floor-0 checkpoints — but the observed RSSI (−63 to −104 dBm) mapped, under the
nominal steep model, to distances up to ~63 m (larger than the 44 m corridor), so
the likelihood pulled particles to wrong distances. We fit the log-distance model
`rssi = RSSI_AT_1M − 10·n·log10(d)` by least squares on 173 (true door→beacon
distance, observed RSSI) pairs across all runs and both floors. The real corridor
path loss is much **flatter** (n ≈ 1.2, typical of multipath-rich indoor
corridors) with a lower reference level.

**Effect:** the Run 1 regression is fixed (BLE 4.44 → 2.02 m, i.e. BLE now *agrees*
with the map rather than fighting it); BLE is well-behaved on all runs. It does not
yet strongly *improve* the door error, because on the single-floor 5c the large
errors come from the floor-1 portions the filter cannot track — BLE's drift
correction should show once floors are added (5d) and error is measured on all
checkpoints.

**Status:** Confirmed. The three parameters remain tunable at the top of `ble.py`.
