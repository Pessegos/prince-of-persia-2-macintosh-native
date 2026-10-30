"""Recovered OnAlert arbitration and its action bodies' input consumption.

Admission (which poses an action body accepts) stays with the scene's
sword actions; pop2/armed_controls.py owns the bank while the sword is drawn.
"""

from dataclasses import replace

from pop2.mac_input import DirectionalInput


def armed_input_request(bank, pose, *, actor_type=0):
    """CODE6:24bc-2584; left/right are Forward/Backward at this boundary."""
    if actor_type in (7, 8):
        return 'special'
    if pose == 161 and bank.modifier >= 0:
        return 'recoil'
    if bank.modifier == -2:
        return 'attack'
    if bank.down < 0:
        # An inadmissible Down still owns this branch: no Up/step fallback.
        return 'sheathe' if pose in (158, 170, 171) else None
    if bank.up < 0:
        return 'block'
    if bank.left < 0:
        return 'advance'
    if bank.right < 0 and bank.modifier == 0:
        return 'retreat'
    return None


def consume_armed_request(bank, request):
    """An accepted action body's words (facing-relative): ClearControls
    4:3e3a and the consumed word, except DoBlock 6:28d4, which consumes Up
    alone. DoStrike 6:280c-2812 consumes Ctrl as 2."""
    if request == 'attack':
        return DirectionalInput(modifier=2)
    if request == 'block':
        return replace(bank, up=1)
    word = {'sheathe': 'down', 'advance': 'left', 'retreat': 'right'}[request]
    return replace(DirectionalInput(modifier=bank.modifier), **{word: 1})


def advance_sequence(level, opponent_room, opponent_column):
    """DoAdvance 6:1e28-1e46: in level five, with the opponent in native room
    19 (port 18) at column 5, the Prince advances with SEQS 86."""
    return 86 if (level, opponent_room, opponent_column) == (5, 18, 5) else None
