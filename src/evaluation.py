import numpy as np
import pandas as pd

import building


REFERENCE_FILE = "assignment/Paths_references.xlsx"

STEP_LENGTH_M = 0.65


REFERENCE_COLUMNS = {
    1: (1, 2, 3, 4, 5),
    2: (7, 8, 9, 10, 11),
    3: (13, 14, 15, 16, 17),
    4: (19, 20, 21, 22, 23),
}


def parse_door(text):
    """
    Split a door label into (floor, room).

    "0 24"  -> (0, "24")
    "1 21a" -> (1, "21a")
    "START" -> (None, "START")
    "END"   -> (None, "END")
    """
    text = str(text).strip()
    if text in ("START", "END"):
        return None, text
    parts = text.split()
    floor = int(parts[0])
    room = parts[1] if len(parts) > 1 else ""
    return floor, room


def find_header_row(raw, number_col):
    for i in range(len(raw)):
        if str(raw.iat[i, number_col]).strip() == "Number":
            return i
    raise ValueError("Could not find the 'Number' header row in the reference file.")


def load_reference(run_id, reference_file=REFERENCE_FILE, start_offset_s=0.0):
    raw = pd.read_excel(reference_file, header=None)

    number_col, time_col, sum_col, door_col, step_col = REFERENCE_COLUMNS[run_id]
    header_row = find_header_row(raw, number_col)

    records = []
    for i in range(header_row + 1, len(raw)):
        number = raw.iat[i, number_col]
        door_raw = raw.iat[i, door_col]

        
        if pd.isna(number) and pd.isna(door_raw):
            continue

        floor, room = parse_door(door_raw)
        time_ms = pd.to_numeric(raw.iat[i, time_col], errors="coerce")
        sum_ms = pd.to_numeric(raw.iat[i, sum_col], errors="coerce")
        sum_steps = pd.to_numeric(raw.iat[i, step_col], errors="coerce")

        records.append({
            "number": int(number) if not pd.isna(number) else None,
            "floor": floor,
            "room": room,
            "time_ms": int(time_ms) if not pd.isna(time_ms) else None,
            "sum_time_ms": int(sum_ms) if not pd.isna(sum_ms) else None,
            "sum_steps": int(sum_steps) if not pd.isna(sum_steps) else None,
            "t_rel": sum_ms / 1000.0 + start_offset_s if not pd.isna(sum_ms) else None,
        })

       
        if room == "END":
            break

    return pd.DataFrame(records)


def error_at_references(trajectory, reference):
    """
    Compare an estimated trajectory against the door reference checkpoints.

    For each checkpoint that has a known door (floor + room), we look up the true
    door position from building.py, interpolate the estimated position to the
    checkpoint's time, and record the distance error. If the trajectory carries a
    `floor` column (the full filter), we also check whether the estimated floor is
    correct; otherwise the estimate is treated as the single floor 0.

    Parameters
    ----------
    trajectory : DataFrame
        Estimated trajectory with columns t_rel, x, y (and optionally floor).
    reference : DataFrame
        A run's reference table (from load_reference).

    Returns
    -------
    DataFrame, one row per checkpoint, with columns:
        number, floor, room, t_rel, est_x, est_y, est_floor,
        true_x, true_y, error_m, floor_correct
    """
    doors = building.door_positions()
    has_floor = "floor" in trajectory.columns
    step_times = trajectory["t_rel"].values

    records = []
    for _, row in reference.iterrows():
        # Skip START / END (no floor) and any checkpoint without a known door.
        if pd.isna(row["floor"]) or pd.isna(row["t_rel"]):
            continue
        key = (row["floor"], row["room"])
        if key not in doors:
            continue

        true_x, true_y, _ = doors[key]
        est_x = float(np.interp(row["t_rel"], trajectory["t_rel"], trajectory["x"]))
        est_y = float(np.interp(row["t_rel"], trajectory["t_rel"], trajectory["y"]))

        if has_floor:
            nearest = int(np.argmin(np.abs(step_times - row["t_rel"])))
            est_floor = int(trajectory["floor"].values[nearest])
        else:
            est_floor = 0

        records.append({
            "number": row["number"],
            "floor": row["floor"],
            "room": row["room"],
            "t_rel": row["t_rel"],
            "est_x": round(est_x, 2),
            "est_y": round(est_y, 2),
            "est_floor": est_floor,
            "true_x": true_x,
            "true_y": true_y,
            "error_m": round(float(np.hypot(est_x - true_x, est_y - true_y)), 2),
            "floor_correct": est_floor == row["floor"],
        })

    return pd.DataFrame(records)


def summary_metrics(per_checkpoint):
    """
    Reduce a per-checkpoint error table (from error_at_references) to a summary.

    Returns
    -------
    dict with mean_error_m, median_error_m, max_error_m, floor_accuracy,
    n_checkpoints.
    """
    error = per_checkpoint["error_m"]
    return {
        "mean_error_m": round(float(error.mean()), 2),
        "median_error_m": round(float(error.median()), 2),
        "max_error_m": round(float(error.max()), 2),
        "floor_accuracy": round(float(per_checkpoint["floor_correct"].mean()), 2),
        "n_checkpoints": int(len(per_checkpoint)),
    }


def compare_metrics(named_trajectories, reference):
    """
    Compare several estimated trajectories on the same door references.

    This is the ablation table: pass the map-only, map+BLE, and full-filter
    trajectories and get their metrics side by side, to see what each fusion
    component contributes. The trajectories are computed by the caller (so this
    module never runs the filter); they may or may not carry a floor column.

    Parameters
    ----------
    named_trajectories : dict
        variant name -> trajectory DataFrame.
    reference : DataFrame
        A run's reference table (from load_reference).

    Returns
    -------
    DataFrame, one row per variant, with columns:
        variant, mean_error_m, median_error_m, max_error_m, floor_accuracy,
        n_checkpoints
    """
    rows = []
    for name, trajectory in named_trajectories.items():
        metrics = summary_metrics(error_at_references(trajectory, reference))
        metrics["variant"] = name
        rows.append(metrics)

    columns = ["variant", "mean_error_m", "median_error_m", "max_error_m",
               "floor_accuracy", "n_checkpoints"]
    return pd.DataFrame(rows)[columns]
