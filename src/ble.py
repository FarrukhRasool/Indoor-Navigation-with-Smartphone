import numpy as np
import pandas as pd



PROJECT_BEACON_PREFIX = "arrive_emi"


def is_project_beacon(beacon_name):
    return str(beacon_name).startswith(PROJECT_BEACON_PREFIX)


def extract_ble_stream(ble_rows, t0_ms):

    stream = ble_rows.copy()

    # Keep only the eight installed project beacons; drop unrelated devices.
    stream = stream[stream["id"].apply(is_project_beacon)]

    # RSSI should be a whole number. Anything unparsable becomes NaN and is dropped.
    stream["rssi"] = pd.to_numeric(stream["rssi"], errors="coerce")
    stream = stream.dropna(subset=["rssi"])
    stream["rssi"] = stream["rssi"].astype(int)

    # Relative time in seconds since the run started (same convention as imu.py).
    stream["t_rel"] = (stream["timestamp_ms"] - t0_ms) / 1000.0

    # Keep only the columns we need, in a clear order, with readable names.
    clean = stream[["timestamp_ms", "t_rel", "id", "address", "rssi"]]
    clean = clean.rename(columns={"timestamp_ms": "t_ms", "id": "beacon"})

    # Make sure observations are in time order and the index is reset.
    clean = clean.sort_values("t_ms").reset_index(drop=True)
    return clean


# ---------------------------------------------------------------------------
# BLE observation model (used by the particle filter later)
#
# Idea: a beacon that is close to the phone is heard with a strong (less
# negative) RSSI; a distant beacon is heard weakly. The log-distance path-loss
# model captures this: the expected RSSI drops with the logarithm of distance.
#
# For one reading we compute, for every particle, the RSSI we would expect if the
# person really stood at that particle, and compare it to the RSSI we actually
# observed. Particles whose expected RSSI matches the observation get a high
# weight; particles that would imply a very different RSSI get a low weight.
#
# "Strong signals weighted more" falls out of this naturally: a strong RSSI is
# only well explained by particles close to the beacon, so it pulls the estimate
# tightly toward the beacon. A weak RSSI is explained by a large far-away region,
# so it is far less discriminating.
# ---------------------------------------------------------------------------


# Path-loss model parameters (nominal indoor values; tune during filter work).
RSSI_AT_1M = -59.0          # expected RSSI one metre from a beacon (dBm)
PATH_LOSS_EXPONENT = 2.5    # how fast RSSI decays with distance (2 = free space)
RSSI_SIGMA = 6.0            # RSSI measurement noise (dBm), width of the likelihood
MIN_DISTANCE_M = 1.0        # floor for distance, avoids log10(0) right at a beacon
FLOOR_PENALTY_M = 6.0       # extra distance when a particle is on the other floor


def expected_rssi(distance_m):
    """
    Expected RSSI at a given distance, using the log-distance path-loss model.

    Works on a single distance or a NumPy array of distances (one per particle).
    """
    distance_m = np.maximum(distance_m, MIN_DISTANCE_M)
    return RSSI_AT_1M - 10.0 * PATH_LOSS_EXPONENT * np.log10(distance_m)


def rssi_likelihood(particle_x, particle_y, particle_floor,
                    beacon_position, observed_rssi):
    """
    Weight each particle by how well its position explains one RSSI reading.

    Parameters
    ----------
    particle_x, particle_y : array-like
        Particle positions in metres (world frame).
    particle_floor : array-like
        Floor index (0 or 1) of each particle.
    beacon_position : tuple
        The observed beacon's (x, y, floor), from building.beacon_positions().
    observed_rssi : float
        The RSSI value actually reported for that beacon at this time.

    Returns
    -------
    numpy array
        One weight per particle (higher = better explains the reading). Weights
        are unnormalised; the filter normalises them across all particles.
    """
    particle_x = np.asarray(particle_x, dtype=float)
    particle_y = np.asarray(particle_y, dtype=float)
    beacon_x, beacon_y, beacon_floor = beacon_position

    horizontal_distance = np.sqrt((particle_x - beacon_x) ** 2
                                  + (particle_y - beacon_y) ** 2)

    # A beacon is normally heard on its own floor, but some signal leaks through
    # the staircases, so a floor mismatch is a soft penalty, not a hard zero.
    floor_mismatch = np.asarray(particle_floor) != beacon_floor
    distance = horizontal_distance + floor_mismatch * FLOOR_PENALTY_M

    predicted_rssi = expected_rssi(distance)
    residual = observed_rssi - predicted_rssi

    # Gaussian likelihood on the RSSI residual.
    return np.exp(-0.5 * (residual / RSSI_SIGMA) ** 2)
