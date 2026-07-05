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
