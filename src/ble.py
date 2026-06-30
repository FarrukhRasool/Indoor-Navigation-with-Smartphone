"""
ble.py
------

Responsible for turning the raw BLE rows of one measurement run into a clean
stream of beacon observations.

In the recorded CSV files there are three BLE-related sources:

    - ble_rssi           : clean, beacon-mapped RSSI readings (what we use)
    - beacon             : raw promiscuous scan of every nearby BLE device
    - live_ble_snapshot  : occasional full snapshot (only a handful of rows)

We use ONLY the "ble_rssi" stream for positioning. The other two are dropped
during the split in preprocessing.py (their counts are kept in the metadata).

The project uses eight installed beacons, all named "arrive_emi...". A scan can
also pick up unrelated BLE devices, so we keep only the project beacons here.

This module only loads and cleans the BLE stream. It does NOT smooth the signal,
normalize RSSI, or map beacons to positions. Beacon positions belong to
building.py and are added later.
"""

import pandas as pd


# All project beacons are named like "arrive_emi1", "arrive_emi8", etc.
PROJECT_BEACON_PREFIX = "arrive_emi"


def is_project_beacon(beacon_name):
    """Return True if a beacon name belongs to the installed project beacons."""
    return str(beacon_name).startswith(PROJECT_BEACON_PREFIX)


def extract_ble_stream(ble_rows, t0_ms):
    """
    Build the clean BLE observation stream from the raw ble_rssi rows.

    Parameters
    ----------
    ble_rows : DataFrame
        All rows of one run where source == "ble_rssi".
    t0_ms : int
        Start timestamp of the run, used to compute relative time in seconds.

    Returns
    -------
    DataFrame with columns: t_ms, t_rel, beacon, address, rssi
        Sorted by time, with non-project beacons and bad RSSI values removed.
        RSSI is kept as the raw integer value (no normalization).
    """
    stream = ble_rows.copy()

    # Keep only the eight installed project beacons; drop unrelated devices.
    stream = stream[stream["id"].apply(is_project_beacon)]

    # RSSI should be a whole number. Anything unparsable becomes NaN and is dropped.
    stream["rssi"] = pd.to_numeric(stream["rssi"], errors="coerce")
    stream = stream.dropna(subset=["rssi"])
    stream["rssi"] = stream["rssi"].astype(int)

    # Relative time in seconds since the run started (same convention as imu.py).
    stream["t_rel"] = (stream["timestamp_ms"] - t0_ms) / 1000.0

    # Keep only the columns we need, in a clear order, with readable names.
    clean = stream[["timestamp_ms", "t_rel", "id", "address", "rssi"]]
    clean = clean.rename(columns={"timestamp_ms": "t_ms", "id": "beacon"})

    # Make sure observations are in time order and the index is reset.
    clean = clean.sort_values("t_ms").reset_index(drop=True)
    return clean
