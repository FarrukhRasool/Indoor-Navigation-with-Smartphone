"""
imu.py
------

Responsible for turning the raw IMU rows of one measurement run into clean,
ready-to-use sensor streams.

In the recorded CSV files, all IMU samples share the same source ("imu") and are
told apart by the "id" column:

    - accel          : raw accelerometer (used later for step detection)
    - gyro           : raw gyroscope (used later for direction changes)
    - mag            : raw magnetometer (used later for heading)
    - imu_processed  : the app's already-filtered IMU signal (comparison only)

This module loads and cleans these streams and derives the motion model from
them: step detection from raw acceleration, and travel direction (heading) from
the gyroscope. It does NOT do BLE handling, building constraints, or the filter
itself. Those belong to other modules.
"""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks


# The four IMU sub-streams we expect, identified by the "id" column.
IMU_TYPES = ["accel", "gyro", "mag", "imu_processed"]


def extract_imu_stream(imu_rows, imu_type, t0_ms):
    """
    Build one clean IMU stream (for example "accel") from the raw IMU rows.

    Parameters
    ----------
    imu_rows : DataFrame
        All rows of one run where source == "imu".
    imu_type : str
        Which sub-stream to extract, e.g. "accel" or "gyro".
    t0_ms : int
        Start timestamp of the run, used to compute relative time in seconds.

    Returns
    -------
    DataFrame with columns: t_ms, t_rel, x, y, z
        Sorted by time, with bad/empty samples removed.
    """
    # Keep only the rows that belong to this sub-stream (e.g. only "accel").
    stream = imu_rows[imu_rows["id"] == imu_type].copy()

    # Convert the axis values to real numbers. Anything unparsable becomes NaN.
    for axis in ["x", "y", "z"]:
        stream[axis] = pd.to_numeric(stream[axis], errors="coerce")

    # Drop samples where any axis is missing.
    stream = stream.dropna(subset=["x", "y", "z"])

    # Relative time in seconds since the run started. Easier to read and plot.
    stream["t_rel"] = (stream["timestamp_ms"] - t0_ms) / 1000.0

    # Keep only the columns we actually need, in a clear order.
    clean = stream[["timestamp_ms", "t_rel", "x", "y", "z"]]
    clean = clean.rename(columns={"timestamp_ms": "t_ms"})

    # Make sure samples are in time order and the index is reset.
    clean = clean.sort_values("t_ms").reset_index(drop=True)
    return clean


def extract_all_imu_streams(imu_rows, t0_ms):
    """
    Build all four IMU streams (accel, gyro, mag, imu_processed) at once.

    Returns
    -------
    dict
        Maps each IMU type name to its cleaned DataFrame.
    """
    streams = {}
    for imu_type in IMU_TYPES:
        streams[imu_type] = extract_imu_stream(imu_rows, imu_type, t0_ms)
    return streams


# ---------------------------------------------------------------------------
# Step detection from raw acceleration
#
# Idea (kept intentionally simple): when a person takes a step, the phone shakes
# and the overall acceleration briefly spikes. We measure the magnitude of the
# acceleration (which ignores phone orientation) and count the spikes as steps.
# ---------------------------------------------------------------------------


def acceleration_magnitude(accel):
    """
    Compute the magnitude of the acceleration for each sample.

    Using the magnitude (length of the x, y, z vector) means the result does not
    depend on how the phone is rotated in the pocket. At rest this value is close
    to gravity (~9.8 m/s^2); during a step it briefly rises above that.
    """
    return np.sqrt(accel["x"] ** 2 + accel["y"] ** 2 + accel["z"] ** 2)


def detect_steps(accel, min_seconds_between_steps=0.3, height_std_factor=1.0):
    """
    Detect steps as peaks in the acceleration magnitude.

    Parameters
    ----------
    accel : DataFrame
        Cleaned accelerometer stream (columns t_ms, t_rel, x, y, z).
    min_seconds_between_steps : float
        Shortest time we allow between two steps. This stops a single step from
        being counted twice.
    height_std_factor : float
        A step peak must rise above `mean + height_std_factor * std` of the
        acceleration magnitude. The default 1.0 matches the counted step totals in
        Paths_references.xlsx to within ~1.5% across the four runs (the counts are
        stable across nearby thresholds). See decision D13.

    Returns
    -------
    DataFrame with columns: step_id, t_ms, t_rel, magnitude
        One row per detected step (a "movement event"), in time order.
    """
    magnitude = acceleration_magnitude(accel)

    # A step peak must rise clearly above the resting gravity level. Using
    # mean + a multiple of the standard deviation adapts to each run instead of a
    # fixed number.
    height_threshold = magnitude.mean() + height_std_factor * magnitude.std()

    # Convert the minimum time gap into a number of samples for find_peaks.
    sampling_rate_hz = len(accel) / (accel["t_rel"].max() - accel["t_rel"].min())
    min_distance_samples = int(min_seconds_between_steps * sampling_rate_hz)

    peak_indices, _ = find_peaks(
        magnitude,
        height=height_threshold,
        distance=min_distance_samples,
    )

    # Turn the detected peaks into a simple list of movement events.
    steps = accel.iloc[peak_indices][["t_ms", "t_rel"]].copy()
    steps["magnitude"] = magnitude.iloc[peak_indices].values
    steps = steps.reset_index(drop=True)
    steps.insert(0, "step_id", range(1, len(steps) + 1))
    return steps


# ---------------------------------------------------------------------------
# Heading (travel direction) from the gyroscope
#
# When the person turns, the phone rotates about the vertical axis. We estimate
# the vertical direction from gravity (the mean acceleration), project the
# gyroscope onto it to get the turning rate, and integrate that rate to get how
# much the heading has changed over time. The phone keeps a roughly constant
# orientation in the pocket during a run, so a single gravity estimate is enough.
# ---------------------------------------------------------------------------


def estimate_gravity_direction(accel):
    """
    Estimate the vertical (gravity) direction in the phone frame.

    Dynamic accelerations from walking average out over a run, so the mean of the
    accelerometer points roughly along gravity. Returned as a unit vector.
    """
    mean = accel[["x", "y", "z"]].mean().values
    return mean / np.linalg.norm(mean)


def heading_from_gyro(gyro, gravity_direction, initial_heading=0.0,
                      remove_bias=True):
    """
    Integrate the gyroscope into a relative heading over time.

    The yaw rate (turning rate about the vertical) is the gyroscope projected onto
    the gravity direction. Integrating it gives the heading change since the
    start. The result is relative: it is anchored by `initial_heading`.

    A small constant bias in the gyroscope would otherwise accumulate into a large
    false rotation over a few minutes. Since the person walks mostly straight
    corridors (yaw rate near zero), the median yaw rate is a good estimate of that
    bias, so we subtract it before integrating.

    Returns
    -------
    DataFrame with columns: t_rel, heading
        Heading in radians in the world frame (0 = east, along +x).
    """
    yaw_rate = (gyro["x"] * gravity_direction[0]
                + gyro["y"] * gravity_direction[1]
                + gyro["z"] * gravity_direction[2])

    if remove_bias:
        yaw_rate = yaw_rate - yaw_rate.median()

    # Integrate rate over time: heading(t) = initial + sum(rate * dt).
    dt = gyro["t_rel"].diff().fillna(0.0)
    heading = initial_heading + (yaw_rate * dt).cumsum()

    return pd.DataFrame({"t_rel": gyro["t_rel"].values, "heading": heading.values})


def build_motion_table(run, step_length=0.65, initial_heading=0.0,
                       heading_sigma_deg=15.0):
    """
    Build the per-step motion table used by the filter later.

    For each detected step we record how far the person moved (step length) and
    in which direction (heading), plus an angular uncertainty that describes the
    "motion sector" of likely travel directions.

    Parameters
    ----------
    run : Run
        A loaded run (uses its accel and gyro streams).
    step_length : float
        Assumed distance covered per step, in metres (kept constant for now).
        The default 0.65 m is the calibrated step length recorded in
        Paths_references.xlsx (65 cm). See decision D10.
    initial_heading : float
        Heading at the start of the run, in radians (0 = east). Anchors the
        otherwise relative gyro heading to the known start direction.
    heading_sigma_deg : float
        Angular uncertainty of each step's direction, in degrees.

    Returns
    -------
    DataFrame with columns: t_rel, step_length, heading, heading_sigma
        One row per detected step.
    """
    steps = detect_steps(run.accel)
    gravity_direction = estimate_gravity_direction(run.accel)
    heading_series = heading_from_gyro(run.gyro, gravity_direction, initial_heading)

    # Look up the heading at each step time.
    step_heading = np.interp(steps["t_rel"],
                             heading_series["t_rel"],
                             heading_series["heading"])

    return pd.DataFrame({
        "t_rel": steps["t_rel"].values,
        "step_length": step_length,
        "heading": step_heading,
        "heading_sigma": np.deg2rad(heading_sigma_deg),
    })


def dead_reckoning(motion_table, start=(0.0, 0.0)):
    """
    Build a simple dead-reckoning trajectory from the motion table.

    This walks step by step from the start point, moving `step_length` along each
    step's `heading`. It uses no BLE and no map, so it drifts over time; it is a
    diagnostic to check that the motion model is sensible before filtering.

    Returns
    -------
    DataFrame with columns: t_rel, x, y
        The start point followed by the position after each step.
    """
    dx = motion_table["step_length"] * np.cos(motion_table["heading"])
    dy = motion_table["step_length"] * np.sin(motion_table["heading"])

    x = start[0] + dx.cumsum()
    y = start[1] + dy.cumsum()

    # Prepend the start point so the trajectory begins where the walk began.
    t_rel = np.concatenate([[motion_table["t_rel"].iloc[0]], motion_table["t_rel"].values])
    xs = np.concatenate([[start[0]], x.values])
    ys = np.concatenate([[start[1]], y.values])

    return pd.DataFrame({"t_rel": t_rel, "x": xs, "y": ys})
