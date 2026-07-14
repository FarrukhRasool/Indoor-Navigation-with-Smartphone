import numpy as np
import pandas as pd
from scipy.signal import find_peaks


# The four IMU sub-streams we expect, identified by the "id" column.
IMU_TYPES = ["accel", "gyro", "mag", "imu_processed"]


def extract_imu_stream(imu_rows, imu_type, t0_ms):

    stream = imu_rows[imu_rows["id"] == imu_type].copy()
    for axis in ["x", "y", "z"]:
        stream[axis] = pd.to_numeric(stream[axis], errors="coerce")

   
    stream = stream.dropna(subset=["x", "y", "z"])
    stream["t_rel"] = (stream["timestamp_ms"] - t0_ms) / 1000.0

   
    clean = stream[["timestamp_ms", "t_rel", "x", "y", "z"]]
    clean = clean.rename(columns={"timestamp_ms": "t_ms"})

    clean = clean.sort_values("t_ms").reset_index(drop=True)
    return clean


def extract_all_imu_streams(imu_rows, t0_ms):
    streams = {}
    for imu_type in IMU_TYPES:
        streams[imu_type] = extract_imu_stream(imu_rows, imu_type, t0_ms)
    return streams


def acceleration_magnitude(accel):
    return np.sqrt(accel["x"] ** 2 + accel["y"] ** 2 + accel["z"] ** 2)


def detect_steps(accel, min_seconds_between_steps=0.3, height_std_factor=1.0):
    magnitude = acceleration_magnitude(accel)
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



def estimate_gravity_direction(accel):
    mean = accel[["x", "y", "z"]].mean().values
    return mean / np.linalg.norm(mean)


def heading_from_gyro(gyro, gravity_direction, initial_heading=0.0,
                      remove_bias=True):
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

