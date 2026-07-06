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


def plot_particle_cloud(trajectory, spread, dead_reckoning=None,
                        run_id=None, ax=None, n_rings=6):
    """
    Plot the motion-only particle-filter estimate.

    Shows the estimated (mean) trajectory and the growing motion uncertainty as
    circles whose radius is the cloud spread at that point. If a dead-reckoning
    path is given, it is drawn too: with no correction the filter mean should sit
    almost on top of it.

    Parameters
    ----------
    trajectory : DataFrame
        Filter estimate (columns t_rel, x, y).
    spread : Series
        Cloud spread (m) per step, aligned with `trajectory`.
    dead_reckoning : DataFrame, optional
        The M3 dead-reckoning path (columns t_rel, x, y) for comparison.
    n_rings : int
        How many uncertainty circles to draw along the path.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 7))

    if dead_reckoning is not None:
        ax.plot(dead_reckoning["x"], dead_reckoning["y"], "--",
                color="gray", linewidth=1.0, label="dead reckoning (M3)")

    ax.plot(trajectory["x"], trajectory["y"], "-",
            color="steelblue", linewidth=1.2, label="particle mean")

    # Uncertainty rings at a few evenly spaced points along the path.
    ring_indices = np.linspace(0, len(trajectory) - 1, n_rings).astype(int)
    for i in ring_indices:
        circle = plt.Circle((trajectory["x"].iloc[i], trajectory["y"].iloc[i]),
                            spread.iloc[i], color="steelblue",
                            fill=False, alpha=0.4, linewidth=0.8)
        ax.add_patch(circle)

    ax.scatter(trajectory["x"].iloc[0], trajectory["y"].iloc[0],
               color="green", s=40, zorder=3, label="start")
    ax.scatter(trajectory["x"].iloc[-1], trajectory["y"].iloc[-1],
               color="red", s=40, zorder=3, label="end")

    title = "Motion-only particle filter (mean + spread)"
    if run_id is not None:
        title += " (Run %d)" % run_id
    ax.set_title(title)
    ax.set_xlabel("x (m) — east")
    ax.set_ylabel("y (m) — north")
    ax.set_aspect("equal")
    ax.legend(loc="upper right")
    return ax


def plot_trajectory_on_corridor(trajectory, corridor_polyline, half_width,
                                run_id=None, ax=None):
    """
    Plot an estimated trajectory on top of the corridor.

    The corridor is drawn as its centre-line plus a translucent thick band that
    suggests the walkable width, so it is easy to see whether the estimate stays
    on the corridor. The band is schematic (drawn in screen units, not exact
    metres); the numeric walkable check is done in the analysis, not the plot.

    Parameters
    ----------
    trajectory : DataFrame
        Estimated trajectory (columns t_rel, x, y).
    corridor_polyline : list of (x, y)
        The corridor centre-line, e.g. from building.corridor_polyline(floor).
    half_width : float
        Corridor half-width in metres (used in the title).
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 5))

    corridor_x = [point[0] for point in corridor_polyline]
    corridor_y = [point[1] for point in corridor_polyline]

    # Schematic corridor band (thick, light) plus a crisp centre-line.
    ax.plot(corridor_x, corridor_y, "-", color="lightsteelblue",
            linewidth=16, alpha=0.5, solid_capstyle="round", zorder=0)
    ax.plot(corridor_x, corridor_y, "--", color="gray", linewidth=1.0,
            zorder=1, label="corridor centre-line")

    ax.plot(trajectory["x"], trajectory["y"], "-", color="steelblue",
            linewidth=1.2, zorder=2, label="estimated trajectory")
    ax.scatter(trajectory["x"].iloc[0], trajectory["y"].iloc[0],
               color="green", s=40, zorder=3, label="start")
    ax.scatter(trajectory["x"].iloc[-1], trajectory["y"].iloc[-1],
               color="red", s=40, zorder=3, label="end")

    title = "Estimated trajectory on the corridor (half-width %.1f m)" % half_width
    if run_id is not None:
        title += " (Run %d)" % run_id
    ax.set_title(title)
    ax.set_xlabel("x (m) — east")
    ax.set_ylabel("y (m) — north")
    ax.set_aspect("equal")
    ax.legend(loc="upper right")
    return ax
