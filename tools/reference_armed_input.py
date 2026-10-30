"""Independent OnAlert request model and its ordinary-Prince action bodies."""

from dataclasses import replace

from tools.reference_input_bank import InputBank


def on_alert(bank, pose, actor_type=0):
    if actor_type in (7, 8):
        return 'special'
    if pose == 161 and bank.modifier >= 0:
        return 'recoil'
    if bank.modifier == -2:
        return 'attack'
    if bank.down < 0:
        return 'sheathe' if pose in (158, 170, 171) else None
    if bank.up < 0:
        return 'block'
    if bank.left < 0:
        return 'advance'
    if bank.right < 0 and bank.modifier == 0:
        return 'retreat'
    return None


def armed_action(bank, pose, *, opponent_pose=0, distance=0, fight=0):
    """OnAlert with its ordinary-Prince action bodies: (bank, events).

    Accepted bodies call ClearControls 4:3e3a and consume their word, except
    DoBlock, which consumes only Up. Refused requests leave every word as it
    was, so a pending request waits for a later admitting pose."""
    del distance  # DoBlock's distance branch is for other actor types.
    request = on_alert(bank, pose)
    if request == 'recoil':
        return bank, (('sequence', 57),)
    if request == 'attack' and pose in (150, 161, 157, 158, 165, 170, 171):
        return InputBank(modifier=2), (('sequence', 66 if pose in (150, 161) else 75),)
    if request == 'sheathe':
        return InputBank(down=1, modifier=bank.modifier), (('sequence', 93 if fight else 92),)
    if request == 'block':
        if pose == 167:
            sequence = 61
        elif pose in (158, 170, 171, 168, 165) and opponent_pose != 168:
            sequence = 62
        else:
            return bank, ()
        return (replace(bank, up=1), (('sequence', sequence),)
                + ((('parry',),) if sequence == 62 and opponent_pose == 153 else ()))
    if request in ('advance', 'retreat') and pose in (158, 170, 171):
        word = 'left' if request == 'advance' else 'right'
        return (replace(InputBank(modifier=bank.modifier), **{word: 1}),
                (('sequence', 56 if request == 'advance' else 57),))
    return bank, ()


def sword_ctrl(bank, *, mode, cell, alert, distance, opponent_type, actor_type, automatic,
               level, room, row, bridge, wounded, bridge_test=False):
    """SwordCtrl 6:2206-2390 for the Prince: (events, bank, automatic flag).

    `cell` is the kind of the Prince's own cell (CurrentCell 4:35a6: 11 loose
    floor, 15 ruins shelf), `alert` the opponent copy's alert word +0x32
    (a5-0x5062), `distance` 4:49ee's result (negative: the opponent is
    behind), `automatic` a5-0x5010 (0 disables the automatic turn),
    `wounded` a pending hit at least as large as the life."""
    if mode >= 2 or wounded:
        return (), bank, automatic
    events, pending = [], True
    # 6:2236-224e: the distance routing runs on a loose floor or shelf, or
    # against an opponent at alert 2 or more; otherwise only step 3 runs.
    if cell in (11, 15) or alert >= 2:
        if -15 <= distance < 331:
            events.append(('alert',))
            pending = False
        elif distance < 0:
            pending = False
            if actor_type == 11:
                pass
            elif not automatic or opponent_type == 6 or (
                    row and level == 5 and room in (10, 7, 12) and bridge_test):
                events.append(('alert',))
            else:
                events.append(('turn',))
    if bank.right < 0 and bank.modifier in (-1, 1) and not (level == 5 and room == 10 and bridge > 0):
        # The voluntary turn: Backward=1 after ClearControls, modifier 2, and
        # the automatic-turn flag toggles (6:2336-2350).
        events.append(('voluntary',))
        return tuple(events), InputBank(right=1, modifier=2), 0 if automatic else 1
    if pending:
        events.append(('sheathe',) if bank.down < 0 else ('alert',))
    return tuple(events), bank, automatic
