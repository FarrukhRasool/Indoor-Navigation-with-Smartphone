"""
evaluation.py
-------------

Responsible for the ground-truth reference data and, later, the error metrics
that compare an estimated trajectory against it.

This file implements the **door-reference loader**. The reference timestamps were
recorded at laboratory doors during each run and stored in
`assignment/Paths_references.xlsx`.

The spreadsheet has four side-by-side blocks, one per run. Each block has six
columns: Number, Time (ms), Sum_Time (ms), Steps, Sum_steps, and Door. `Steps` is
the number of steps taken during that segment (derived from the segment time and
the walking pace), `Sum_steps` is the running total, and Door is written as
"<floor> <room>" (for example "0 24" = floor 0, room 024), except for the START
and END markers. A separate cell records the calibrated step length in cm.

This module does NOT run the filter or draw plots. Metric functions and the
metric (x, y) positions of each door will be added later (the door positions
come from building.py).
"""

import pandas as pd


# The reference workbook (path is relative to the project root).
REFERENCE_FILE = "assignment/Paths_references.xlsx"

# For each run, the spreadsheet columns (0-indexed) that hold
# Number, Time (ms), Sum_Time (ms), Steps, Sum_steps, and Door. The blocks are
# side by side, each six columns wide, separated by a spacer column.
REFERENCE_COLUMNS = {
    1: (1, 2, 3, 4, 5, 6),
    2: (8, 9, 10, 11, 12, 13),
    3: (15, 16, 17, 18, 19, 20),
    4: (22, 23, 24, 25, 26, 27),
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
        number, floor, room, time_ms, sum_time_ms, steps, sum_steps, t_rel
        One row per checkpoint, in order, including START and END.
    """
    # Read the whole sheet without a header so we can address columns by position.
    raw = pd.read_excel(reference_file, header=None)

    (number_col, time_col, sum_col,
     steps_col, sum_steps_col, door_col) = REFERENCE_COLUMNS[run_id]
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
        steps = pd.to_numeric(raw.iat[i, steps_col], errors="coerce")
        sum_steps = pd.to_numeric(raw.iat[i, sum_steps_col], errors="coerce")

        records.append({
            "number": int(number) if not pd.isna(number) else None,
            "floor": floor,
            "room": room,
            "time_ms": int(time_ms) if not pd.isna(time_ms) else None,
            "sum_time_ms": int(sum_ms) if not pd.isna(sum_ms) else None,
            "steps": round(float(steps), 3) if not pd.isna(steps) else None,
            "sum_steps": round(float(sum_steps), 3) if not pd.isna(sum_steps) else None,
            "t_rel": sum_ms / 1000.0 + start_offset_s if not pd.isna(sum_ms) else None,
        })

        # The END marker is the last checkpoint of a run.
        if room == "END":
            break

    return pd.DataFrame(records)


def load_step_length_m(reference_file=REFERENCE_FILE):
    """
    Read the calibrated step length (in metres) from the reference workbook.

    The workbook records it in a labelled cell ("Step lenght (cm)") with the value
    in a neighbouring cell on the same row; we convert from centimetres to metres.
    """
    raw = pd.read_excel(reference_file, header=None)
    for i in range(len(raw)):
        for j in range(raw.shape[1]):
            text = str(raw.iat[i, j]).strip().lower()
            if text.startswith("step") and "cm" in text:
                for k in range(j + 1, raw.shape[1]):
                    value = pd.to_numeric(raw.iat[i, k], errors="coerce")
                    if not pd.isna(value):
                        return float(value) / 100.0
    raise ValueError("Could not find the step length in the reference file.")
