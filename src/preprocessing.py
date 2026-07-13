"""
preprocessing.py
----------------

The single orchestrator of the data pipeline.

For one measurement run it:

    1. loads the raw CSV file,
    2. splits the rows by source (imu / ble_rssi / beacon / live_ble_snapshot),
    3. asks imu.py and ble.py to build the clean streams,
    4. computes one shared time origin (t0) for the whole run,
    5. collects simple metadata (counts, dropped rows, beacon stats, duration),
    6. flags any byte-identical duplicate runs (without removing them),
    7. returns everything bundled in a Run object.

This module does NOT do filtering, step detection, or modeling. It only loads,
splits, cleans (through imu.py / ble.py), and describes the data.
"""

from dataclasses import dataclass
import hashlib
import os

import pandas as pd

import imu
import ble


# Where the raw recordings live and how their files are named.
RAW_DATA_DIR = "data/raw"
RUN_FILE_PATTERN = "Record_data_path_{run_id}.csv"

# The four measurement runs we recorded.
KNOWN_RUN_IDS = [1, 2, 3, 4]

# Known start conditions for each run, used to initialise the filter. The
# assignment allows fixing the start point; the start position comes from the
# documented path descriptions (see docs/experiment_protocol.md), and the initial
# heading is calibrated by aligning each run's first straight corridor leg to the
# known corridor axis (this absorbs the unknown pocket-mounting yaw offset; see
# decision D11). Heading is in radians in the world frame (0 = east, +y = north).
RUN_START = {
    1: {"start": (0.0, 0.0),  "floor": 0, "initial_heading": 0.5603},
    2: {"start": (17.5, 0.0), "floor": 0, "initial_heading": 0.1808},
    3: {"start": (33.0, 0.0), "floor": 0, "initial_heading": -2.3083},
    4: {"start": (2.0, 0.0),  "floor": 0, "initial_heading": 2.5722},
}


@dataclass
class Run:
    """
    One cleaned measurement run.

    The IMU and BLE streams are kept separate (no merging) but share the same
    time origin, so t_rel is comparable across them. This event-driven layout is
    exactly what a particle/Kalman filter needs later.
    """
    run_id: int
    t0_ms: int
    duration_s: float
    accel: pd.DataFrame          # raw accelerometer (used for step detection)
    gyro: pd.DataFrame           # raw gyroscope
    mag: pd.DataFrame            # raw magnetometer
    imu_processed: pd.DataFrame  # app-filtered IMU (comparison only)
    ble: pd.DataFrame            # clean beacon RSSI observations
    meta: dict                   # counts, dropped rows, beacon stats, flags


def run_file_path(run_id, raw_dir=RAW_DATA_DIR):
    """Return the CSV path for a given run id."""
    return os.path.join(raw_dir, RUN_FILE_PATTERN.format(run_id=run_id))


def hash_file(path):
    """Return the MD5 checksum of a file, used to detect identical runs."""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def find_duplicate_runs(run_id, raw_dir=RAW_DATA_DIR):
    """
    Find other runs whose raw file is byte-for-byte identical to this one.

    Returns a list of run ids (empty if the run is unique). It compares MD5 file
    hashes, so it catches an accidental duplicate recording (as happened with an
    early Run 2 submission, since replaced with the correct file).
    """
    this_hash = hash_file(run_file_path(run_id, raw_dir))
    duplicates = []
    for other_id in KNOWN_RUN_IDS:
        if other_id == run_id:
            continue
        other_path = run_file_path(other_id, raw_dir)
        if os.path.exists(other_path) and hash_file(other_path) == this_hash:
            duplicates.append(other_id)
    return duplicates


def build_metadata(raw_df, source_counts, imu_streams, ble_stream,
                   duplicate_with):
    """
    Collect simple, human-readable facts about the run.

    This is descriptive only: it never changes the data, it just summarizes it.
    """
    # How many BLE rows were dropped as non-project beacons or bad values.
    ble_rssi_rows = source_counts.get("ble_rssi", 0)
    ble_dropped = ble_rssi_rows - len(ble_stream)

    # Largest time gap between two consecutive BLE readings (signal loss hint).
    if len(ble_stream) > 1:
        max_ble_gap_s = ble_stream["t_rel"].diff().max()
    else:
        max_ble_gap_s = 0.0

    meta = {
        "n_raw_rows": len(raw_df),
        "source_counts": source_counts,
        "imu_counts": {name: len(df) for name, df in imu_streams.items()},
        "ble_clean_rows": len(ble_stream),
        "ble_dropped_rows": ble_dropped,
        "beacons_seen": sorted(ble_stream["beacon"].unique().tolist()),
        "beacon_obs_counts": ble_stream["beacon"].value_counts().to_dict(),
        "rssi_min": int(ble_stream["rssi"].min()) if len(ble_stream) else None,
        "rssi_max": int(ble_stream["rssi"].max()) if len(ble_stream) else None,
        "max_ble_gap_s": round(float(max_ble_gap_s), 3),
        "is_duplicate": len(duplicate_with) > 0,
        "duplicate_with": duplicate_with,
    }
    return meta


def load_run(run_id, raw_dir=RAW_DATA_DIR):
    """
    Load and clean one measurement run, returning a Run object.

    This is the function notebooks should call. It re-uses imu.py and ble.py so
    the cleaning logic lives in one place each.
    """
    # 1. Load the raw recording.
    raw_df = pd.read_csv(run_file_path(run_id, raw_dir))

    # 2. Split rows by source. We only keep imu and ble_rssi for the pipeline;
    #    beacon and live_ble_snapshot are dropped but still counted below.
    source_counts = raw_df["source"].value_counts().to_dict()
    imu_rows = raw_df[raw_df["source"] == "imu"]
    ble_rows = raw_df[raw_df["source"] == "ble_rssi"]

    # 3. Compute one shared time origin for the run: the earliest timestamp
    #    among the streams we actually keep (IMU and BLE).
    t0_ms = int(min(imu_rows["timestamp_ms"].min(),
                    ble_rows["timestamp_ms"].min()))
    t_end_ms = int(max(imu_rows["timestamp_ms"].max(),
                       ble_rows["timestamp_ms"].max()))
    duration_s = (t_end_ms - t0_ms) / 1000.0

    # 4. Build the clean streams through the dedicated modules.
    imu_streams = imu.extract_all_imu_streams(imu_rows, t0_ms)
    ble_stream = ble.extract_ble_stream(ble_rows, t0_ms)

    # 5. Detect duplicate runs and collect descriptive metadata.
    duplicate_with = find_duplicate_runs(run_id, raw_dir)
    meta = build_metadata(raw_df, source_counts,
                          imu_streams, ble_stream, duplicate_with)

    # 6. Bundle everything into the Run object.
    return Run(
        run_id=run_id,
        t0_ms=t0_ms,
        duration_s=duration_s,
        accel=imu_streams["accel"],
        gyro=imu_streams["gyro"],
        mag=imu_streams["mag"],
        imu_processed=imu_streams["imu_processed"],
        ble=ble_stream,
        meta=meta,
    )
