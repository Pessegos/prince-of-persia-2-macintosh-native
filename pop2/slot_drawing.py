"""Compose a cavern/ruins room drawing from its piece-drawer slots.

The import (`tools/extract_slots.py`) records which (row, column, pass) drawer
call admitted each original drawing command and, for the slots that read a
dynamic cell, their fragment for each state of those cells. A room's command
list is the concatenation of its slots' fragments in drawer order, then
DumpTable's stable layer order (3:2c1e-2c68).
"""

# The export harness's drawer order: RedrawCellFast visits rows bottom-up,
# then the upper border row, each column, then the passes (back 0, back 5,
# CUST back 11, front 1; the climbing and floor redraws use front pass 2).
SLOT_ORDER = tuple((row, column, draw_pass) for row in (2, 1, 0, -1) for column in range(10)
                   for draw_pass in (0, 5, 11, 1, 2))

# A bridge plank unit: rest, wobbling up (nibble 1), down (2), fallen (3).
PLANK_STATES = 4


def draw_order_key(layer, kind):
    # DumpTable 3:2c1e-2c68 paints back-wall records (kind 0) before
    # floor/pillar bodies, regardless of their admission order.
    return layer == 'front', kind != 0 if layer == 'back' else False


def compose(fragments):
    """Commands from {slot: [[command, kind], ...]} in the original order."""
    admitted = [item for slot in SLOT_ORDER for item in fragments.get(slot, ())]
    return [command for command, kind in sorted(admitted, key=lambda item: draw_order_key(item[0][0], item[1]))]


def compose_list(record, states):
    """One exported list (`base` and dependent `tables`) for unit states."""
    fragments = {tuple(slot): fragment for slot, fragment in record['base']}
    for slot, depends, table in record['tables']:
        fragments[tuple(slot)] = table[','.join(str(states[unit]) for unit in depends)]
    return compose(fragments)


def clip_climbing(commands, rect):
    # ComputeHalfRect 3:3690-36fc: each climbing pose clips the source
    # pose's repaint by its own top/right bounds.
    result = []
    for command in commands:
        column, row = command[8:10]
        clip = list(command[6])
        clip[0] = max(clip[0], row * 120 + rect[0])
        clip[3] = min(clip[3], column * 51 + rect[3])
        if clip[0] < clip[2] and clip[1] < clip[3]:
            copied = list(command)
            copied[6] = clip
            result.append(copied)
    return result
