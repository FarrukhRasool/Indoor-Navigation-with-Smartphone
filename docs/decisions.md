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

## D4 — Metric scale is nominal

**Decision:** Since no exact building dimensions were available, distances are
derived from a nominal door spacing (4.5 m) and corridor width (2 m). All the
numbers are constants at the top of `building.py` and can be adjusted.

**Why:** We only need internal consistency for the filter; absolute scale can be
refined later if a real dimension becomes available.

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
