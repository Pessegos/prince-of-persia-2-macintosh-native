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
