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

This module only loads and cleans these streams. It does NOT do step detection,
BLE handling, or filtering. Those belong to other modules.
"""

import pandas as pd


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
