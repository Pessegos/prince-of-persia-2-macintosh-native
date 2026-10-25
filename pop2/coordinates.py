"""Explicit conversions between the original's and the port's coordinates.

- Actor X: the original's character X includes a 207-pixel origin (the
  column table a5-0x4b88 holds 207 + 51 * column); the port's scene X does not.
- Rooms: the original numbers rooms from 1 (0 means none); the port from 0.
- Columns: `character_column` (CODE:4 3ad6 -> 5:48b0) converts an actor X;
  callers decide whether that X is the actor's own X or its supporting foot
  (`floor_contact_x`). There is deliberately no single generic column helper.
"""

NATIVE_X_ORIGIN = 207
TILE_WIDTH = 51


def native_x(scene_x):
    """The original's character X for a port scene X."""
    return scene_x + NATIVE_X_ORIGIN


def scene_x(native):
    """The port's scene X for the original's character X."""
    return native - NATIVE_X_ORIGIN


def column_left(column):
    """Scene X of the original column table entry (a5-0x4b88[column] - 207)."""
    return column * TILE_WIDTH


def native_room(room):
    """The original's one-based room number for a port room index."""
    return room + 1


def port_room(room):
    """The port's room index for an original room number; None for room 0."""
    return room - 1 if room else None
