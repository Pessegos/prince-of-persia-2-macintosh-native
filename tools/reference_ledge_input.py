"""Independent input-only ledge gate; terrain/support decisions are boundaries."""


def ledge_request(bank, *, grip=0, alive=-1, sequence_mode=0):
    if alive >= 0:
        return 'release'
    if grip == 0 and bank.up:
        return 'climb'
    if bank.modifier == 0 or sequence_mode == 11:
        return 'release'
    return None


def climb_input(bank):
    return bank.consume('up', clear=True, modifier=1)


def release_input(bank):
    return bank.consume('down', clear=True)
