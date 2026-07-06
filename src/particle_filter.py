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
