"""Independent unarmed input routing; geometry/action bodies are boundaries."""

from tools.reference_input_bank import InputBank


def unarmed_route(bank, pose, *, mode=0, sequence=201, sword=0):
    """Return the bank and ordered action requests from the bounded GenCtrl.

    Prince actor10/type0, alive, no alert auto-draw or object pickup. Action
    bodies are no-op sinks, so only resets performed by the router occur.
    Latches are already facing-relative, after native input normalization.
    """
    if mode in (4, 5, 9) or sequence in (27, 110):
        return bank.clear_directions(), ()
    f, b, u, d, m = bank.words()
    if pose == 15 or 50 <= pose <= 52:
        if sword != -1 and m == -2 and not any((f, b, u, d)):
            return bank.clear_directions().consume(modifier=2), (('draw',), ('target',))
        if m in (-1, 1):
            if b < 0:
                return bank, (('turn',),)
            if u < 0:
                return bank, (('up',),)
            if d < 0:
                return bank, (('down',),)
            if f < 0 and not u and not d:
                return bank, (('step', 0),)
            if f:
                return bank, ()
        if f < 0:
            return bank, ((('forward_jump',) if u < 0 else ('run',)),)
        if b < 0:
            return bank, (('turn',),)
        if u < 0:
            return bank, (('up',),)
        if d < 0:
            return bank, (('down',),)
        return bank, (('run',),) if f else ()
    if 45 <= pose <= 49:
        accepted = pose == 48 and m >= 0 and f and not u and not d
        return bank, (('sequence', 43),) if accepted else ()
    if 1 <= pose <= 3:
        if f < 0 and u < 0:
            return bank.clear_directions().consume('left', 'up'), (('forward_jump',),)
        return bank, ()
    if 67 <= pose <= 69:
        return bank, (('forward_jump',),) if f else ()
    if 4 <= pose <= 14:
        if not f and not b and pose in (7, 11):
            bank, events = bank.clear_directions().consume('left'), (('sequence', 13),)
        elif b:
            bank, events = bank.clear_directions().consume('right'), (('sequence', 6),)
        elif u:
            events = (('run_jump', 4),) if u < 0 else ()
        elif d < 0:
            bank, events = bank.clear_directions().consume('down'), (('sequence', 26),)
        else:
            events = ()
        if bank.left < 0:
            bank = bank.consume('left')
        return bank, events
    if pose in (26, 44):
        bank = bank.clear_directions()
    return bank, ()


def sampled_route(bank, axes, pose, *, facing_right=False, inverted=False, **kwargs):
    """Sample in keyboard coordinates, orient, route, then restore old facing."""
    sampled = bank.sample(*axes).remap(facing_right=facing_right, inverted=inverted)
    result, events = unarmed_route(sampled, pose, **kwargs)
    return result.remap(facing_right=facing_right, inverted=inverted), events


EMPTY_BANK = InputBank()
