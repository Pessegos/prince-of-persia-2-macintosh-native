"""The order DrawObjs draws the frame's objects in (CODE:3).

DrawObjs 3:39d6 draws only when it is called with -1 (3:39e6): the calls for
each redrawn cell (3:1ed6) and for bucket 30 (3:326a) return at once, and the
one call after every cell (3:3326) draws the whole object table. It lists the
objects from the last added to the first (3:3a02-3a26) and SortObjTable 3:3b62
bubble-sorts that list, at most 1001 passes, swapping a pair when CompareObj
3:3bec says the first is drawn after the second. Cells play no part in the
order: they choose which scenery is redrawn, not when an object is drawn.

Objects are AddCharObj 3:0130 characters (kind = the character type for the
Prince, opponent types 1, 6, 7, 8 and 10, otherwise 2, SetupOpponent
3:0f10-0f44; the hit burst and the temple flame are kind 5, the shadow's
flame 14) and AddMobObj 5:346a moving objects (kind = MOB type | 0x80). X is
+0 (ConvertX 4:33e6), Y the bottom at +2, the pose at +8.
"""

from dataclasses import dataclass
from typing import Any

# GetObjForePriority 3:3e24: DATA a5-0x44e0 by character kind, a5-0x44c2 by
# MOB type. A higher priority is drawn first, so further back.
CHARACTER_PRIORITY = (127, 127, 127, 127, 127, 50, 127, 127, 127, 127, 127, 127, 127, 200, 200)
MOB_PRIORITY = (127, 0, 127, 127, 200, 60, 225, 50, 200, 80, 210, 210, 60, 200, 0, 0)
MOB = 0x80
# CompareObj 3:3cdc-3ce6: heads (kinds 7/8) in these poses go behind the rest.
HEAD_BACK_POSES = (0xb5, 0xa6)
# 3:3bc2-3bd2 tests the pass count before adding one: 1001 passes at most.
SORT_PASSES = 1001


@dataclass(frozen=True)
class DrawObject:
    x: int
    y: int
    kind: int
    frame: int = 0
    item: Any = None


def character_kind(actor_type):
    """AddCharObj's kind for a character of this type (3:0dbe, 3:0f10-0f44)."""
    return actor_type if actor_type in (0, 1, 6, 7, 8, 10) else 2


def mob_kind(mob_type):
    return MOB | mob_type


def fore_priority(kind):
    """GetObjForePriority 3:3e24."""
    if kind & MOB:
        return MOB_PRIORITY[kind & 0x7f]
    return CHARACTER_PRIORITY[kind]


def _normal(kind):
    # 3:3c26-3c32: kinds 4 and 6 compare as 2.
    return 2 if kind in (4, 6) else kind


def _sorted_behind(kind, frame):
    return kind in (3, 9) or kind in (7, 8) and frame in HEAD_BACK_POSES


def draws_after(a, b):
    """CompareObj 3:3bec: whether ``a``, listed before ``b``, is drawn after it."""
    first, second = _normal(a.kind), _normal(b.kind)
    if first == second:
        # 3:3c84-3cbc: the same kind, bottom then X.
        if a.y == b.y:
            return a.x > b.x
        return a.y > b.y
    # 3:3cc0-3d46: attachments and heads in their back poses go first. The
    # first object's own test (3:3ce8-3cfc) reads its kind only.
    if _sorted_behind(second, b.frame) and first not in (3, 9, 7, 8):
        return True
    if _sorted_behind(first, a.frame) and second not in (3, 9, 7, 8):
        return False
    priority_a, priority_b = fore_priority(first), fore_priority(second)
    if priority_a != priority_b:
        return priority_a < priority_b
    if a.y == b.y:
        return a.x > b.x
    if first & MOB or second & MOB:
        # 3:3d82-3da4: against a moving object the lower bottom goes first.
        return a.y < b.y
    if first == 0 and second == 3 or first == 2 and second == 9:
        return False
    if second == 0 and first == 3 or second == 2 and first == 9:
        return True
    return a.y > b.y


def sort_objects(objects):
    """The objects in DrawObjs' drawing order, given in the order they were added."""
    order = list(reversed(objects))
    for _pass in range(SORT_PASSES):
        swapped = False
        for index in range(len(order) - 1):
            if draws_after(order[index], order[index + 1]):
                order[index], order[index + 1] = order[index + 1], order[index]
                swapped = True
        if not swapped:
            break
    return order
