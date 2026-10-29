"""Independent OnAlert request model, with action bodies supplied as sinks."""


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
