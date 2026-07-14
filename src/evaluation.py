import pandas as pd


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
