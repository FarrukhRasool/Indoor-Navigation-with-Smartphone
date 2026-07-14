import numpy as np
import matplotlib.pyplot as plt

import imu


def plot_acceleration_with_steps(accel, steps, run_id=None, ax=None):
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


def plot_step_count_comparison(steps, reference, run_id=None, ax=None):
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 4))

    detected_cumulative = np.arange(1, len(steps) + 1)
    ax.plot(steps["t_rel"], detected_cumulative, color="steelblue",
            linewidth=1.2, label="detected (cumulative)")

    marked = reference[reference["sum_steps"].notna()]
    ax.scatter(marked["t_rel"], marked["sum_steps"], color="red", s=30, zorder=3,
               label="counted reference")

    title = "Detected vs counted cumulative steps"
    if run_id is not None:
        title += " (Run %d)" % run_id
    ax.set_title(title)
    ax.set_xlabel("time since run start (s)")
    ax.set_ylabel("cumulative steps")
    ax.legend(loc="upper left")
    return ax


def plot_particle_cloud(trajectory, spread, dead_reckoning=None,
                        run_id=None, ax=None, n_rings=6):
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
                                beacons=None, run_id=None, ax=None):
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 5))

    corridor_x = [point[0] for point in corridor_polyline]
    corridor_y = [point[1] for point in corridor_polyline]

    # Schematic corridor band (thick, light) plus a crisp centre-line.
    ax.plot(corridor_x, corridor_y, "-", color="lightsteelblue",
            linewidth=16, alpha=0.5, solid_capstyle="round", zorder=0)
    ax.plot(corridor_x, corridor_y, "--", color="gray", linewidth=1.0,
            zorder=1, label="corridor centre-line")

    if beacons is not None:
        beacon_x = [position[0] for position in beacons.values()]
        beacon_y = [position[1] for position in beacons.values()]
        ax.scatter(beacon_x, beacon_y, marker="^", color="darkorange",
                   s=70, zorder=4, label="beacons")
        for name, (bx, by, _) in beacons.items():
            ax.annotate(name.replace("arrive_", ""), (bx, by),
                        textcoords="offset points", xytext=(0, 7),
                        fontsize=8, ha="center", color="darkorange")

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


def _draw_corridor(ax, corridor_polyline):
    """Draw the corridor centre-line and a schematic width band on an axis."""
    corridor_x = [point[0] for point in corridor_polyline]
    corridor_y = [point[1] for point in corridor_polyline]
    ax.plot(corridor_x, corridor_y, "-", color="lightsteelblue",
            linewidth=16, alpha=0.5, solid_capstyle="round", zorder=0)
    ax.plot(corridor_x, corridor_y, "--", color="gray", linewidth=1.0, zorder=1)


def plot_floor_over_time(trajectory, reference=None, run_id=None, ax=None):
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 2.5))

    ax.step(trajectory["t_rel"], trajectory["floor"], where="post",
            color="steelblue", linewidth=1.5, label="estimated floor")

    if reference is not None:
        known = reference[reference["floor"].notna()]
        ax.scatter(known["t_rel"], known["floor"], color="red", s=25, zorder=3,
                   label="reference checkpoints")

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["floor 0", "floor 1"])
    ax.set_ylim(-0.3, 1.3)
    title = "Estimated floor over time"
    if run_id is not None:
        title += " (Run %d)" % run_id
    ax.set_title(title)
    ax.set_xlabel("time since run start (s)")
    ax.legend(loc="center right")
    return ax


def plot_trajectory_two_floors(trajectory, corridor_polyline, half_width,
                               beacons=None, run_id=None):
    fig, axes = plt.subplots(2, 1, figsize=(9, 7))
    for floor_index, ax in zip([1, 0], axes):   
        _draw_corridor(ax, corridor_polyline)

        segment = trajectory[trajectory["floor"] == floor_index]
        ax.scatter(segment["x"], segment["y"], s=8, color="steelblue",
                   zorder=2, label="estimate on floor %d" % floor_index)

        if beacons is not None:
            floor_beacons = {name: pos for name, pos in beacons.items()
                             if pos[2] == floor_index}
            if floor_beacons:
                bx = [pos[0] for pos in floor_beacons.values()]
                by = [pos[1] for pos in floor_beacons.values()]
                ax.scatter(bx, by, marker="^", color="darkorange", s=70,
                           zorder=4, label="beacons")

        ax.set_title("Floor %d" % floor_index)
        ax.set_ylabel("y (m)")
        ax.set_aspect("equal")
        ax.legend(loc="upper right", fontsize=8)
    axes[-1].set_xlabel("x (m) — east")

    if run_id is not None:
        fig.suptitle("Estimated trajectory by floor (Run %d)" % run_id)
    fig.tight_layout()
    return fig
