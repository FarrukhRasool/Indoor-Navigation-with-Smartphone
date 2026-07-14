
from dataclasses import dataclass
import hashlib
import os

import pandas as pd

import imu
import ble



RAW_DATA_DIR = "data/raw"
RUN_FILE_PATTERN = "Record_data_path_{run_id}.csv"


KNOWN_RUN_IDS = [1, 2, 3, 4]


RUN_START = {
    1: {"start": (0.0, 0.0),   "floor": 0, "initial_heading": 0.8151},
    2: {"start": (21.6, 0.0),  "floor": 0, "initial_heading": 0.2250},
    3: {"start": (42.0, 0.0),  "floor": 0, "initial_heading": -1.6555},
    4: {"start": (0.0, 0.0),   "floor": 0, "initial_heading": 2.6722},
}


@dataclass
class Run:

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
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def find_duplicate_runs(run_id, raw_dir=RAW_DATA_DIR):

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
    
    ble_rssi_rows = source_counts.get("ble_rssi", 0)
    ble_dropped = ble_rssi_rows - len(ble_stream)

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

    raw_df = pd.read_csv(run_file_path(run_id, raw_dir))
    source_counts = raw_df["source"].value_counts().to_dict()
    imu_rows = raw_df[raw_df["source"] == "imu"]
    ble_rows = raw_df[raw_df["source"] == "ble_rssi"]

    t0_ms = int(min(imu_rows["timestamp_ms"].min(),
                    ble_rows["timestamp_ms"].min()))
    t_end_ms = int(max(imu_rows["timestamp_ms"].max(),
                       ble_rows["timestamp_ms"].max()))
    duration_s = (t_end_ms - t0_ms) / 1000.0

   
    imu_streams = imu.extract_all_imu_streams(imu_rows, t0_ms)
    ble_stream = ble.extract_ble_stream(ble_rows, t0_ms)

   
    duplicate_with = find_duplicate_runs(run_id, raw_dir)
    meta = build_metadata(raw_df, source_counts,
                          imu_streams, ble_stream, duplicate_with)

   
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
