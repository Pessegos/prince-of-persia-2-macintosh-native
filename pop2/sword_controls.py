"""Recovered OnAlert arbitration and a bridge for existing armed buffering.

This selects requests, not their action-body admission or lifetime. The host
armed buffer/repeat policy remains explicit until its bank migration.
"""

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


_REQUEST_WORD = {'sword_attack': 'modifier', 'sword_sheathe': 'down',
                 'sword_block': 'up', 'sword_advance': 'left', 'sword_retreat': 'right'}


def buffered_sword_request(current, incoming):
    """Arbitrate existing requests at the eventual guard gate, not this pose.

Only the winner occupies the old host slot. This does not invent another
queue, alter the rapid-attack filter, or claim native armed bank ownership.
Unrelated/scripted commands retain their existing replacement behavior.
"""
    if current not in _REQUEST_WORD or incoming not in _REQUEST_WORD:
        return incoming
    words = {_REQUEST_WORD[kind]: -2 if kind == 'sword_attack' else -1
             for kind in (current, incoming)}
    return 'sword_' + armed_input_request(DirectionalInput(**words), 158)
