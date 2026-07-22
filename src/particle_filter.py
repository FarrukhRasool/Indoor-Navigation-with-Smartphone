import numpy as np
import pandas as pd



STEP_LENGTH_SIGMA_M = 0.15
START_SPREAD_M = 0.5
WALL_SIGMA_M = 0.1
FLOOR_CHANGE_PROB = 0.15


def initialise_particles(start, n_particles, rng, spread=START_SPREAD_M):
    x = rng.normal(start[0], spread, n_particles)
    y = rng.normal(start[1], spread, n_particles)
    return x, y


def predict(x, y, step, rng, length_sigma=STEP_LENGTH_SIGMA_M):
    n = len(x)
    length = rng.normal(step.step_length, length_sigma, n)
    heading = rng.normal(step.heading, step.heading_sigma, n)

    x = x + length * np.cos(heading)
    y = y + length * np.sin(heading)
    return x, y


def estimate(x, y):
    return x.mean(), y.mean()


def cloud_spread(x, y):
    mx, my = x.mean(), y.mean()
    return np.sqrt(np.mean((x - mx) ** 2 + (y - my) ** 2))


def run_motion_only(run, motion_table, start, n_particles=500, seed=0,
                    length_sigma=STEP_LENGTH_SIGMA_M):
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


def constraint_weights(x, y, floor, building, wall_sigma=WALL_SIGMA_M):
    weights = np.empty(len(x))
    for i in range(len(x)):
        distance = building.distance_to_corridor(x[i], y[i], floor)
        overshoot = max(0.0, distance - building.CORRIDOR_HALF_WIDTH_M)
        weights[i] = np.exp(-0.5 * (overshoot / wall_sigma) ** 2)
    return weights


def effective_sample_size(weights):
    total = weights.sum()
    if total == 0:
        return 0.0
    normalised = weights / total
    return 1.0 / np.sum(normalised ** 2)


def systematic_resample_indices(weights, rng):
    n = len(weights)
    positions = (rng.random() + np.arange(n)) / n
    cumulative = np.cumsum(weights / weights.sum())
    return np.searchsorted(cumulative, positions)


def resample(x, y, weights, rng):
    indices = systematic_resample_indices(weights, rng)
    return x[indices], y[indices]


def run_with_constraints(run, motion_table, start, building, floor=0,
                         n_particles=500, seed=0,
                         length_sigma=STEP_LENGTH_SIGMA_M,
                         wall_sigma=WALL_SIGMA_M):
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

def run_with_ble(run, motion_table, start, building, ble, floor=0,
                 n_particles=500, seed=0, length_sigma=STEP_LENGTH_SIGMA_M,
                 wall_sigma=WALL_SIGMA_M):
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
    spreads = []
    n_resamples = 0
    for step in motion_table.itertuples(index=False):
        x, y = predict(x, y, step, rng, length_sigma)

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


def maybe_change_floor(x, y, floor, building, rng, p=FLOOR_CHANGE_PROB):
    floor = floor.copy()
    for i in range(len(x)):
        if building.can_change_floor(x[i], y[i]) and rng.random() < p:
            floor[i] = 1 - floor[i]
    return floor


def estimate_floor(floor, weights):
    return int(round(np.average(floor, weights=weights)))


def run_filter(run, motion_table, start, floor, building, ble,
               n_particles=500, seed=0, length_sigma=STEP_LENGTH_SIGMA_M,
               wall_sigma=WALL_SIGMA_M, floor_change_prob=FLOOR_CHANGE_PROB):
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
