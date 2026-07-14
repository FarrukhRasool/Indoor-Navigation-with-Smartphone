import math



DOOR_SPACING_M = 5.25       
CORRIDOR_HALF_WIDTH_M = 1.0   
WEST_OFFSET_M = 8.5           
MAIN_CORRIDOR_LENGTH_M = 44.0 
EAST_STUB_LENGTH_M = 6.0     
STAIRCASE_RADIUS_M = 3.0     


ROOM_ORDER_WEST_TO_EAST = ["24", "23", "22", "21", "20", "19", "18"]

# Centres of the two staircases (shared by both floors).
WEST_STAIRCASE = (0.0, 0.0)
EAST_STAIRCASE = (MAIN_CORRIDOR_LENGTH_M, -EAST_STUB_LENGTH_M + 1.0)



def corridor_polyline(floor):
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
    polyline = corridor_polyline(floor)
    distances = []
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:]):
        distances.append(_distance_point_to_segment(x, y, ax, ay, bx, by))
    return min(distances)


def is_walkable(x, y, floor):
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
