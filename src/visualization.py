"""
visualization.py
-----------------

Responsible for plotting. It draws IMU signals, BLE signals, trajectories, and
evaluation graphs.

It does NOT compute anything (no filtering, no step detection). It only takes
already-prepared data and shows it.
"""

import numpy as np
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


def plot_heading(heading_series, run_id=None, ax=None):
    """
    Plot the estimated heading (travel direction) over time, in degrees.

    Straight corridor walking shows up as flat segments; turns show up as steps
    (a turnaround is about 180 degrees).
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 3))

    ax.plot(heading_series["t_rel"], np.degrees(heading_series["heading"]),
            color="darkorange", linewidth=1.0)

    title = "Estimated heading over time"
    if run_id is not None:
        title += " (Run %d)" % run_id
    ax.set_title(title)
    ax.set_xlabel("time since run start (s)")
    ax.set_ylabel("heading (degrees)")
    return ax


def plot_dead_reckoning(trajectory, run_id=None, ax=None):
    """
    Plot a dead-reckoning trajectory (x, y) in metres.

    This is the raw motion model with no map or BLE correction, so it is expected
    to drift; it only checks that the motion model produces a sensible shape.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 7))

    ax.plot(trajectory["x"], trajectory["y"], "-", color="steelblue", linewidth=1.0)
    ax.scatter(trajectory["x"].iloc[0], trajectory["y"].iloc[0],
               color="green", s=40, zorder=3, label="start")
    ax.scatter(trajectory["x"].iloc[-1], trajectory["y"].iloc[-1],
               color="red", s=40, zorder=3, label="end")

    title = "Dead-reckoning trajectory (no map / no BLE)"
    if run_id is not None:
        title += " (Run %d)" % run_id
    ax.set_title(title)
    ax.set_xlabel("x (m) — east")
    ax.set_ylabel("y (m) — north")
    ax.set_aspect("equal")
    ax.legend(loc="upper right")
    return ax
