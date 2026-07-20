"""
particle_filter.py
------------------

The particle filter: the core that estimates position over time by fusing the
IMU motion model, the BLE observations, and the building constraints.

This file currently implements sub-step 5a: a MOTION-ONLY filter on a single
floor. It moves a cloud of particles using the per-step motion table (from
imu.py) and reports the cloud's mean position over time. There is no BLE
correction, no building constraint, and no floor change yet -- those are added in
the later sub-steps (5b-5d).

Because there is no measurement to correct the motion, the particle weights stay
uniform and the cloud simply spreads out. That growing spread is exactly the
"error-prone motion sector" the assignment describes, and it is the scaffolding
the BLE update and map constraints plug into next.

For 5a a particle is just its position (x, y); heading is taken fresh from the
motion table on each step. Persistent per-particle heading and floor are added in
the later sub-steps that need them.

This module does NOT load or parse data and does NOT draw plots.
"""

import numpy as np
import pandas as pd


# Extra noise added to each step length (metres). The heading noise comes from
# the motion table's own heading_sigma, so it is not repeated here.
STEP_LENGTH_SIGMA_M = 0.15

# Spread of the initial particle cloud around the (fixed) start position.
START_SPREAD_M = 0.5

# How quickly a particle's weight decays once it strays outside the corridor.
# A narrow value acts as a nearly hard wall: it strongly favours particles that
# stay on the corridor when resampling (see docs/decisions.md, D9). Tunable.
WALL_SIGMA_M = 0.1

# Per-step probability that a particle inside a staircase zone switches floor.
# Small enough to avoid constant flip-flopping, large enough to let the cloud
# change floor during the few steps spent in a staircase (see decision D12).
FLOOR_CHANGE_PROB = 0.15


def initialise_particles(start, n_particles, rng, spread=START_SPREAD_M):
    """
    Create a cloud of particles around the known start position.

    The assignment allows fixing the start point, so we scatter the particles
    with a small Gaussian spread around it to represent our start uncertainty.

    Returns
    -------
    (x, y) : two NumPy arrays of length n_particles.
    """
    x = rng.normal(start[0], spread, n_particles)
    y = rng.normal(start[1], spread, n_particles)
    return x, y


def predict(x, y, step, rng, length_sigma=STEP_LENGTH_SIGMA_M):
    """
    Move every particle by one step of the motion table.

    Each particle draws its own step length and heading from Gaussians centred on
    the step's values, so the cloud fans out into the likely "motion sector".

    Parameters
    ----------
    x, y : NumPy arrays
        Current particle positions.
    step : one motion-table row (has step_length, heading, heading_sigma).
    rng : NumPy random generator.

    Returns
    -------
    (x, y) : the moved particle positions.
    """
    n = len(x)
    length = rng.normal(step.step_length, length_sigma, n)
    heading = rng.normal(step.heading, step.heading_sigma, n)

    x = x + length * np.cos(heading)
    y = y + length * np.sin(heading)
    return x, y


def estimate(x, y):
    """Return the mean position of the cloud (its point estimate)."""
    return x.mean(), y.mean()


def cloud_spread(x, y):
    """
    Return the spread of the cloud: the root-mean-square distance of the
    particles from their mean, in metres. Used to watch the motion uncertainty
    grow over time.
    """
    mx, my = x.mean(), y.mean()
    return np.sqrt(np.mean((x - mx) ** 2 + (y - my) ** 2))


def run_motion_only(run, motion_table, start, n_particles=500, seed=0,
                    length_sigma=STEP_LENGTH_SIGMA_M):
    """
    Run the motion-only particle filter over one run (sub-step 5a).

    Starting from a cloud around `start`, it predicts on every step of the motion
    table and records the cloud mean and spread after each step.

    Parameters
    ----------
    run : Run
        The loaded run (kept for interface consistency with later sub-steps;
        the motion is taken from `motion_table`).
    motion_table : DataFrame
        Per-step motion (t_rel, step_length, heading, heading_sigma) from imu.py.
    start : (x, y)
        The known start position in world metres.
    n_particles : int
        Number of particles.
    seed : int
        Random seed, so the result is reproducible.

    Returns
    -------
    trajectory : DataFrame with columns t_rel, x, y
        The estimated (mean) position after each step.
    spread : Series
        The cloud spread (m) at each step, aligned with `trajectory`.
    """
    rng = np.random.default_rng(seed)
    x, y = initialise_particles(start, n_particles, rng)

    times = []
    xs = []
    ys = []
    spreads = []
    for step in motion_table.itertuples(index=False):
        x, y = predict(x, y, step, rng, length_sigma)
        mx, my = estimate(x, y)
        times.append(step.t_rel)
        xs.append(mx)
        ys.append(my)
        spreads.append(cloud_spread(x, y))

    trajectory = pd.DataFrame({"t_rel": times, "x": xs, "y": ys})
    spread = pd.Series(spreads, name="spread")
    return trajectory, spread


# ---------------------------------------------------------------------------
# 5b: building constraints (soft map-aware weighting + resampling)
#
# The motion model alone drifts off the corridors. Here we weight each particle
# by how walkable its position is: particles inside the corridor keep full weight,
# particles that stray outside are down-weighted (a soft wall, not a hard cut).
# When a few particles end up carrying most of the weight, we resample so the
# cloud concentrates on the walkable positions. The next motion step re-spreads
# the duplicated particles, so the cloud keeps its diversity.
# ---------------------------------------------------------------------------


def constraint_weights(x, y, floor, building, wall_sigma=WALL_SIGMA_M):
    """
    Weight each particle by how walkable its position is.

    A particle inside the corridor gets weight 1. Outside, the weight decays as a
    Gaussian in how far past the corridor half-width it sits, so off-corridor
    particles are down-weighted but not immediately killed.

    Parameters
    ----------
    x, y : NumPy arrays of particle positions.
    floor : int
        The floor the particles are on (single floor for 5b).
    building : module
        The building model, passed in so this file does not import it directly.

    Returns
    -------
    NumPy array of weights, one per particle.
    """
    weights = np.empty(len(x))
    for i in range(len(x)):
        distance = building.distance_to_corridor(x[i], y[i], floor)
        overshoot = max(0.0, distance - building.CORRIDOR_HALF_WIDTH_M)
        weights[i] = np.exp(-0.5 * (overshoot / wall_sigma) ** 2)
    return weights


def effective_sample_size(weights):
    """
    Effective number of particles (ESS).

    A low ESS means a few particles carry most of the weight, which is when we
    should resample. Expects non-negative weights (not necessarily normalised).
    """
    total = weights.sum()
    if total == 0:
        return 0.0
    normalised = weights / total
    return 1.0 / np.sum(normalised ** 2)


def systematic_resample_indices(weights, rng):
    """
    Return the particle indices chosen by systematic resampling.

    Systematic resampling uses a single random offset and evenly spaced sample
    points, which is simple and keeps the sample well spread. Returning indices
    (rather than the resampled arrays) lets the caller apply the same selection to
    several per-particle arrays at once (x, y, and later floor).
    """
    n = len(weights)
    positions = (rng.random() + np.arange(n)) / n
    cumulative = np.cumsum(weights / weights.sum())
    return np.searchsorted(cumulative, positions)


def resample(x, y, weights, rng):
    """
    Resample the (x, y) particles in proportion to their weights.

    Likely positions are duplicated and unlikely ones are dropped; the returned
    particles are unweighted again.
    """
    indices = systematic_resample_indices(weights, rng)
    return x[indices], y[indices]


def run_with_constraints(run, motion_table, start, building, floor=0,
                         n_particles=500, seed=0,
                         length_sigma=STEP_LENGTH_SIGMA_M,
                         wall_sigma=WALL_SIGMA_M):
    """
    Motion + building-constraint particle filter on a single floor (sub-step 5b).

    Each step: move the particles, weight them by walkability, record the weighted
    mean, and resample when the effective sample size drops below half.

    Parameters
    ----------
    run : Run
        The loaded run (kept for interface consistency with later sub-steps).
    motion_table : DataFrame
        Per-step motion from imu.py.
    start : (x, y)
        The known start position in world metres.
    building : module
        The building model (geometry + constraints).
    floor : int
        Which floor the particles are on (single floor for 5b).

    Returns
    -------
    trajectory : DataFrame with columns t_rel, x, y
        The estimated (weighted-mean) position after each step.
    spread : Series
        The cloud spread (m) at each step.
    n_resamples : int
        How many times resampling happened (a simple diagnostic).
    """
    rng = np.random.default_rng(seed)
    x, y = initialise_particles(start, n_particles, rng)

    times = []
    xs = []
    ys = []
    spreads = []
    n_resamples = 0
    for step in motion_table.itertuples(index=False):
        x, y = predict(x, y, step, rng, length_sigma)

        weights = constraint_weights(x, y, floor, building, wall_sigma)

        # Weighted-mean estimate. Guard the rare case where every particle is off
        # the corridor (all weights zero) by falling back to the plain mean.
        if weights.sum() > 0:
            estimate_x = np.average(x, weights=weights)
            estimate_y = np.average(y, weights=weights)
        else:
            estimate_x, estimate_y = estimate(x, y)

        times.append(step.t_rel)
        xs.append(estimate_x)
        ys.append(estimate_y)
        spreads.append(cloud_spread(x, y))

        # Resample when a few particles dominate the cloud.
        if weights.sum() > 0 and effective_sample_size(weights) < n_particles / 2:
            x, y = resample(x, y, weights, rng)
            n_resamples += 1

    trajectory = pd.DataFrame({"t_rel": times, "x": xs, "y": ys})
    spread = pd.Series(spreads, name="spread")
    return trajectory, spread, n_resamples


# ---------------------------------------------------------------------------
# 5c: BLE correction (sensor fusion)
#
# The map constraint alone cannot fix heading drift, because it has no absolute
# reference. Here we add one: whenever a BLE reading arrives, we multiply each
# particle's weight by the BLE observation likelihood (ble.py) -- how well that
# particle's position explains the observed RSSI. Strong readings pull the cloud
# firmly toward the beacon, correcting the drift.
#
# This is the same loop as run_with_constraints, with just one addition: the BLE
# readings that fall inside each step interval are applied as extra weight
# factors. BLE is event-driven, so a reading only affects the estimate at the
# moment it actually arrives.
# ---------------------------------------------------------------------------


def run_with_ble(run, motion_table, start, building, ble, floor=0,
                 n_particles=500, seed=0, length_sigma=STEP_LENGTH_SIGMA_M,
                 wall_sigma=WALL_SIGMA_M):
    """
    Motion + building constraints + BLE correction on a single floor (5c).

    Parameters
    ----------
    run : Run
        Provides the BLE stream (run.ble).
    motion_table : DataFrame
        Per-step motion from imu.py.
    start : (x, y)
        Known start position in world metres.
    building : module
        Building model (corridor constraint + beacon positions).
    ble : module
        BLE model, used for its rssi_likelihood function.
    floor : int
        Which floor the particles are on (single floor for 5c).

    Returns
    -------
    trajectory : DataFrame with columns t_rel, x, y
    spread : Series
    n_resamples : int
    """
    rng = np.random.default_rng(seed)
    x, y = initialise_particles(start, n_particles, rng)
    particle_floor = np.full(n_particles, floor)

    beacon_positions = building.beacon_positions()

    # The BLE readings as plain arrays, walked through in time order.
    ble_t = run.ble["t_rel"].values
    ble_beacon = run.ble["beacon"].values
    ble_rssi = run.ble["rssi"].values
    ble_index = 0

    times = []
    xs = []
    ys = []
    spreads = []
    n_resamples = 0
    for step in motion_table.itertuples(index=False):
        x, y = predict(x, y, step, rng, length_sigma)

        weights = constraint_weights(x, y, floor, building, wall_sigma)

        # Apply every BLE reading that has arrived up to this step's time.
        while ble_index < len(ble_t) and ble_t[ble_index] <= step.t_rel:
            position = beacon_positions.get(ble_beacon[ble_index])
            if position is not None:
                weights = weights * ble.rssi_likelihood(
                    x, y, particle_floor, position, ble_rssi[ble_index])
            ble_index += 1

        # Weighted-mean estimate, with the same all-zero-weight guard as 5b.
        if weights.sum() > 0:
            estimate_x = np.average(x, weights=weights)
            estimate_y = np.average(y, weights=weights)
        else:
            estimate_x, estimate_y = estimate(x, y)

        times.append(step.t_rel)
        xs.append(estimate_x)
        ys.append(estimate_y)
        spreads.append(cloud_spread(x, y))

        if weights.sum() > 0 and effective_sample_size(weights) < n_particles / 2:
            x, y = resample(x, y, weights, rng)
            n_resamples += 1

    trajectory = pd.DataFrame({"t_rel": times, "x": xs, "y": ys})
    spread = pd.Series(spreads, name="spread")
    return trajectory, spread, n_resamples


# ---------------------------------------------------------------------------
# 5d: floor transitions (the full filter)
#
# A person can only move between floors at a staircase. We give each particle a
# floor and let it switch floor -- only when it is inside a staircase zone -- with
# a small probability each step. This creates competing floor hypotheses at the
# staircases; the BLE update then keeps whichever particles are on the floor whose
# beacons match the reading, and the map keeps them on the corridor. No barometer
# or explicit stair detection is needed: the filter resolves the floor itself.
# ---------------------------------------------------------------------------


def maybe_change_floor(x, y, floor, building, rng, p=FLOOR_CHANGE_PROB):
    """
    Let particles switch floor, but only inside a staircase zone.

    For each particle in a staircase zone (building.can_change_floor), flip its
    floor (0<->1) with probability p. Particles elsewhere keep their floor. The BLE
    update then keeps whichever particles are on the floor whose beacons match the
    reading, so the filter resolves the floor itself.

    Returns
    -------
    A new floor array (the input is not modified).
    """
    floor = floor.copy()
    for i in range(len(x)):
        if building.can_change_floor(x[i], y[i]) and rng.random() < p:
            floor[i] = 1 - floor[i]
    return floor


def estimate_floor(floor, weights):
    """Weighted majority floor (0 or 1)."""
    return int(round(np.average(floor, weights=weights)))


def run_filter(run, motion_table, start, floor, building, ble,
               n_particles=500, seed=0, length_sigma=STEP_LENGTH_SIGMA_M,
               wall_sigma=WALL_SIGMA_M, floor_change_prob=FLOOR_CHANGE_PROB):
    """
    The full particle filter: motion + building constraints + BLE + floor changes.

    This is run_with_ble plus a per-particle floor that may change at staircases.

    Parameters
    ----------
    run : Run
        Provides the BLE stream (run.ble).
    motion_table : DataFrame
        Per-step motion from imu.py (built with the run's initial heading).
    start : (x, y)
        Known start position in world metres.
    floor : int
        Floor the person starts on (all particles start here).
    building : module
        Building model (corridor constraint, staircases, beacon positions).
    ble : module
        BLE model, used for its rssi_likelihood function.

    Returns
    -------
    trajectory : DataFrame with columns t_rel, x, y, floor
    spread : Series
    n_resamples : int
    """
    rng = np.random.default_rng(seed)
    x, y = initialise_particles(start, n_particles, rng)
    particle_floor = np.full(n_particles, floor)

    beacon_positions = building.beacon_positions()

    ble_t = run.ble["t_rel"].values
    ble_beacon = run.ble["beacon"].values
    ble_rssi = run.ble["rssi"].values
    ble_index = 0

    times = []
    xs = []
    ys = []
    floors = []
    spreads = []
    n_resamples = 0
    for step in motion_table.itertuples(index=False):
        x, y = predict(x, y, step, rng, length_sigma)
        particle_floor = maybe_change_floor(x, y, particle_floor, building, rng,
                                            floor_change_prob)

        # Both floors share the same corridor footprint, so walkability does not
        # depend on the floor; we evaluate the map constraint once. The BLE update
        # then uses each particle's own floor, so cross-floor beacons are penalised.
        weights = constraint_weights(x, y, floor, building, wall_sigma)

        while ble_index < len(ble_t) and ble_t[ble_index] <= step.t_rel:
            position = beacon_positions.get(ble_beacon[ble_index])
            if position is not None:
                weights = weights * ble.rssi_likelihood(
                    x, y, particle_floor, position, ble_rssi[ble_index])
            ble_index += 1

        if weights.sum() > 0:
            estimate_x = np.average(x, weights=weights)
            estimate_y = np.average(y, weights=weights)
            estimate_fl = estimate_floor(particle_floor, weights)
        else:
            estimate_x, estimate_y = estimate(x, y)
            estimate_fl = int(round(particle_floor.mean()))

        times.append(step.t_rel)
        xs.append(estimate_x)
        ys.append(estimate_y)
        floors.append(estimate_fl)
        spreads.append(cloud_spread(x, y))

        if weights.sum() > 0 and effective_sample_size(weights) < n_particles / 2:
            indices = systematic_resample_indices(weights, rng)
            x, y = x[indices], y[indices]
            particle_floor = particle_floor[indices]
            n_resamples += 1

    trajectory = pd.DataFrame({"t_rel": times, "x": xs, "y": ys, "floor": floors})
    spread = pd.Series(spreads, name="spread")
    return trajectory, spread, n_resamples
