"""
particle_filter.py
------------------

The particle filter: the core that estimates position over time by fusing the
IMU motion model, the BLE observations, and the building constraints.

This file currently implements sub-steps 5a and 5b on a single floor:

    - 5a (run_motion_only): move a cloud of particles using the per-step motion
      table (from imu.py) and report the cloud's mean over time. No correction,
      so the weights stay uniform and the cloud just spreads out.
    - 5b (run_with_constraints): add the building map as a soft constraint. Each
      step, particles are weighted by how walkable their position is, the estimate
      is the weighted mean, and the cloud is resampled when a few particles start
      to dominate. This keeps the estimate on the corridors.

There is still no BLE correction and no floor change yet -- those are added in the
later sub-steps (5c, 5d). The weighting-and-resampling machinery added here is the
same one 5c reuses: 5c simply multiplies in the BLE likelihood as a second weight.

For now a particle is just its position (x, y); heading is taken fresh from the
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
# stay on the corridor when resampling. A sweep over the four runs found ~0.1 m
# works best (see docs/decisions.md, D9); wider walls constrain too weakly.
WALL_SIGMA_M = 0.1


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


def resample(x, y, weights, rng):
    """
    Systematic resampling.

    Draw a new set of particles in proportion to their weights, so likely
    positions are duplicated and unlikely ones are dropped. Systematic resampling
    uses a single random offset and evenly spaced sample points, which is simple
    and keeps the sample well spread. The returned particles are unweighted again.
    """
    n = len(x)
    positions = (rng.random() + np.arange(n)) / n
    cumulative = np.cumsum(weights / weights.sum())
    indices = np.searchsorted(cumulative, positions)
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
