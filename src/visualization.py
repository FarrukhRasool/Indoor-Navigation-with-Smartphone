"""
visualization.py
-----------------

Responsible for plotting. It draws IMU signals, BLE signals, trajectories, and
evaluation graphs.

It does NOT compute anything (no filtering, no step detection). It only takes
already-prepared data and shows it.
"""

import matplotlib.pyplot as plt

import imu


def plot_acceleration_with_steps(accel, steps, run_id=None, ax=None):
    """
    Plot the acceleration magnitude over time and mark the detected steps.

    Parameters
    ----------
    accel : DataFrame
        Cleaned accelerometer stream (columns t_ms, t_rel, x, y, z).
    steps : DataFrame
        Detected step events (columns step_id, t_ms, t_rel, magnitude).
    run_id : int, optional
        Used only for the plot title.
    ax : matplotlib Axes, optional
        Draw on an existing axis; if None, a new figure is created.
    """
    magnitude = imu.acceleration_magnitude(accel)

    if ax is None:
        _, ax = plt.subplots(figsize=(12, 4))

    # The continuous acceleration magnitude signal.
    ax.plot(accel["t_rel"], magnitude, linewidth=0.8,
            color="steelblue", label="acceleration magnitude")

    # A red dot on each detected step.
    ax.scatter(steps["t_rel"], steps["magnitude"],
               color="red", s=20, zorder=3,
               label="detected step (%d)" % len(steps))

    title = "Acceleration magnitude and detected steps"
    if run_id is not None:
        title += " (Run %d)" % run_id
    ax.set_title(title)
    ax.set_xlabel("time since run start (s)")
    ax.set_ylabel("acceleration (m/s^2)")
    ax.legend(loc="upper right")
    return ax
