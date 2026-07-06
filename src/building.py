"""
building.py
-----------

Represents the two-floor building for the position estimate: the walkable
corridors, the door positions (reference points), the beacon positions, and the
staircase zones where floor changes are allowed.

The building is modelled simply. Each floor is one long main corridor plus a
short stub leading to the east staircase. We describe the walkable space as a
centre-line (a poly-line) with a half-width: a point is walkable if it lies
within the half-width of the corridor centre-line.

Coordinate system (see docs/architecture.md):
    - origin (0, 0) at the west staircase, floor 0
    - x axis = east (along the main corridor), y axis = north
    - units = metres
    - floor is a separate index (0 = lower/ground, 1 = upper)

The metric scale is approximate: no exact building dimensions were available, so
distances are derived from a nominal door spacing. All the tunable numbers are
constants at the top of this file.

This module only describes geometry and answers validity questions. It does NOT
load sensor data, run the filter, or plot.
"""

import math


# --- Tunable geometry (approximate, easy to adjust) -------------------------

DOOR_SPACING_M = 4.5          # distance between two neighbouring main doors
CORRIDOR_HALF_WIDTH_M = 1.0   # half of the corridor width (corridor is ~2 m)
WEST_OFFSET_M = 4.0           # west staircase -> first door (room 24 / 124)
MAIN_CORRIDOR_LENGTH_M = 35.0 # west staircase -> east end of the main corridor
EAST_STUB_LENGTH_M = 5.0      # east end -> east staircase (short south stub)
STAIRCASE_RADIUS_M = 3.0      # radius of a staircase zone (floor-change area)

# The seven main doors along the corridor, listed west -> east. Both floors use
# the same room labels; the floor index distinguishes 018 from 118, etc.
ROOM_ORDER_WEST_TO_EAST = ["24", "23", "22", "21", "20", "19", "18"]

# Centres of the two staircases (shared by both floors).
WEST_STAIRCASE = (0.0, 0.0)
EAST_STAIRCASE = (MAIN_CORRIDOR_LENGTH_M, -EAST_STUB_LENGTH_M + 1.0)


# --- Corridor geometry ------------------------------------------------------

def corridor_polyline(floor):
    """
    Return the corridor centre-line for a floor as a list of (x, y) points.

    Both floors have the same footprint: a horizontal main corridor plus a short
    stub going south to the east staircase.
    """
    return [
        (0.0, 0.0),                                    # west staircase
        (MAIN_CORRIDOR_LENGTH_M, 0.0),                 # east end of main corridor
        (MAIN_CORRIDOR_LENGTH_M, -EAST_STUB_LENGTH_M), # east staircase stub
    ]


def _distance_point_to_segment(px, py, ax, ay, bx, by):
    """Shortest distance from point (px, py) to the segment a-b."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        # The segment is a single point.
        return math.hypot(px - ax, py - ay)
    # Project the point onto the segment, clamped to the segment ends.
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nearest_x = ax + t * dx
    nearest_y = ay + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def distance_to_corridor(x, y, floor):
    """
    Shortest distance from (x, y) to the corridor centre-line of a floor.

    Zero on the centre-line, growing as the point moves away from it. This is the
    building's single source of truth for "how far off the corridor is a point",
    used both by is_walkable and by the particle filter's soft wall constraint.
    """
    polyline = corridor_polyline(floor)
    distances = []
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:]):
        distances.append(_distance_point_to_segment(x, y, ax, ay, bx, by))
    return min(distances)


def is_walkable(x, y, floor):
    """
    Return True if (x, y) on the given floor lies inside a corridor.

    A point is walkable if it is within the corridor half-width of the
    centre-line poly-line.
    """
    return distance_to_corridor(x, y, floor) <= CORRIDOR_HALF_WIDTH_M


def can_change_floor(x, y):
    """
    Return True if (x, y) is inside a staircase zone.

    Floor changes are only allowed here (west or east staircase).
    """
    for cx, cy in (WEST_STAIRCASE, EAST_STAIRCASE):
        if math.hypot(x - cx, y - cy) <= STAIRCASE_RADIUS_M:
            return True
    return False


# --- Reference points: doors and beacons ------------------------------------

def door_positions():
    """
    Return the reference door positions as a dict keyed by (floor, room).

    Doors are placed on the corridor centre-line (y = 0) at the point where a
    person stands when passing that door. Both floors share the same seven main
    doors; floor 1 has an extra door "21a" between rooms "22" and "21".

    Example key/value: (0, "24") -> (4.0, 0.0, 0)
    """
    doors = {}
    for index, room in enumerate(ROOM_ORDER_WEST_TO_EAST):
        x = WEST_OFFSET_M + index * DOOR_SPACING_M
        doors[(0, room)] = (x, 0.0, 0)
        doors[(1, room)] = (x, 0.0, 1)

    # Floor 1 also has room "21a", located between "22" and "21".
    x_22 = doors[(1, "22")][0]
    x_21 = doors[(1, "21")][0]
    doors[(1, "21a")] = ((x_22 + x_21) / 2, 0.0, 1)
    return doors


def beacon_positions():
    """
    Return the six installed beacons as a dict: name -> (x, y, floor).

    These are the beacons marked in red on the path sketches (emi1, 2, 3, 4, 8,
    10). Three sit on each floor: west end, middle, and east end of the corridor.
    """
    x_west = 2.0
    x_middle = WEST_OFFSET_M + 3 * DOOR_SPACING_M   # ~ room 21 / 121 (centre)
    x_east = MAIN_CORRIDOR_LENGTH_M - 2.0           # just before the east stub

    return {
        # floor 0
        "arrive_emi8": (x_west, 0.0, 0),
        "arrive_emi10": (x_middle, 0.0, 0),
        "arrive_emi4": (x_east, 0.0, 0),
        # floor 1
        "arrive_emi1": (x_west, 0.0, 1),
        "arrive_emi2": (x_middle, 0.0, 1),
        "arrive_emi3": (x_east, 0.0, 1),
    }
