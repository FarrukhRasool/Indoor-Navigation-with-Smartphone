import numpy as np
import pandas as pd



PROJECT_BEACON_PREFIX = "arrive_emi"


def is_project_beacon(beacon_name):
    return str(beacon_name).startswith(PROJECT_BEACON_PREFIX)


def extract_ble_stream(ble_rows, t0_ms):

    stream = ble_rows.copy()

    stream = stream[stream["id"].apply(is_project_beacon)]

    
    stream["rssi"] = pd.to_numeric(stream["rssi"], errors="coerce")
    stream = stream.dropna(subset=["rssi"])
    stream["rssi"] = stream["rssi"].astype(int)

    
    stream["t_rel"] = (stream["timestamp_ms"] - t0_ms) / 1000.0

   
    clean = stream[["timestamp_ms", "t_rel", "id", "address", "rssi"]]
    clean = clean.rename(columns={"timestamp_ms": "t_ms", "id": "beacon"})

   
    clean = clean.sort_values("t_ms").reset_index(drop=True)
    return clean


RSSI_AT_1M = -76.5         
PATH_LOSS_EXPONENT = 1.19  
RSSI_SIGMA = 6.5            
MIN_DISTANCE_M = 1.0        
FLOOR_PENALTY_M = 6.0       


def expected_rssi(distance_m):

    distance_m = np.maximum(distance_m, MIN_DISTANCE_M)
    return RSSI_AT_1M - 10.0 * PATH_LOSS_EXPONENT * np.log10(distance_m)


def rssi_likelihood(particle_x, particle_y, particle_floor,
                    beacon_position, observed_rssi):
    particle_x = np.asarray(particle_x, dtype=float)
    particle_y = np.asarray(particle_y, dtype=float)
    beacon_x, beacon_y, beacon_floor = beacon_position

    horizontal_distance = np.sqrt((particle_x - beacon_x) ** 2
                                  + (particle_y - beacon_y) ** 2)

    floor_mismatch = np.asarray(particle_floor) != beacon_floor
    distance = horizontal_distance + floor_mismatch * FLOOR_PENALTY_M

    predicted_rssi = expected_rssi(distance)
    residual = observed_rssi - predicted_rssi

    return np.exp(-0.5 * (residual / RSSI_SIGMA) ** 2)
