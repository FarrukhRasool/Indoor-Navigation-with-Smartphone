"""
evaluation.py
-------------

Responsible for the ground-truth reference data and, later, the error metrics
that compare an estimated trajectory against it.

This file implements the **door-reference loader**. The reference timestamps were
recorded at laboratory doors during each run and stored in
`assignment/Paths_references.xlsx`.

The spreadsheet has four side-by-side blocks, one per run. Each block has five
columns: Number, Time (ms), Sum_Time (ms), Door, and Step. `Step` is the running
total number of steps counted up to that checkpoint (counted during recording, not
derived), and Door is written as "<floor> <room>" (for example "0 24" = floor 0,
room 024), except for the START and END markers.

This module does NOT run the filter or draw plots. Metric functions and the
metric (x, y) positions of each door will be added later (the door positions
come from building.py).
"""

import pandas as pd


# The reference workbook (path is relative to the project root).
REFERENCE_FILE = "assignment/Paths_references.xlsx"

# Measured step length (stride), in metres. An earlier version of the workbook
# recorded it as 65 cm; the current version omits the cell, so we keep it here.
STEP_LENGTH_M = 0.65

# For each run, the spreadsheet columns (0-indexed) that hold
# Number, Time (ms), Sum_Time (ms), Door, and Step. The blocks are side by side,
# each five columns wide, separated by a spacer column.
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
    """
    Find the row index where a run block's header ("Number") sits.

    Data rows start on the following row.
    """
    for i in range(len(raw)):
        if str(raw.iat[i, number_col]).strip() == "Number":
            return i
    raise ValueError("Could not find the 'Number' header row in the reference file.")


def load_reference(run_id, reference_file=REFERENCE_FILE, start_offset_s=0.0):
    """
    Load the door reference checkpoints for one run.

    Parameters
    ----------
    run_id : int
        Which run (1..4).
    reference_file : str
        Path to the reference spreadsheet.
    start_offset_s : float
        Seconds to add when aligning the reference clock to the processed
        timeline. It is 0 for Runs 1, 3, 4 (their recording starts at the START
        checkpoint). Run 2 needs a small positive offset, to be determined later
        from the first walking motion.

    Returns
    -------
    DataFrame with columns:
        number, floor, room, time_ms, sum_time_ms, sum_steps, t_rel
        One row per checkpoint, in order, including START and END. `sum_steps` is
        the counted cumulative step total at that checkpoint.
    """
    # Read the whole sheet without a header so we can address columns by position.
    raw = pd.read_excel(reference_file, header=None)

    number_col, time_col, sum_col, door_col, step_col = REFERENCE_COLUMNS[run_id]
    header_row = find_header_row(raw, number_col)

    records = []
    for i in range(header_row + 1, len(raw)):
        number = raw.iat[i, number_col]
        door_raw = raw.iat[i, door_col]

        # Skip fully empty rows (blocks have different lengths).
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

        # The END marker is the last checkpoint of a run.
        if room == "END":
            break

    return pd.DataFrame(records)
