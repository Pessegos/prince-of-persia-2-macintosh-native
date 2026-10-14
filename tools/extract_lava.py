"""Read the Macintosh lava tables during import, without shipping CODE/DATA."""

import struct

from pop2.mac_resources import parse_resource_fork
from tools.extract_enemy_profiles import expand_a5_data


def lava_tables(program, caverns):
    data = expand_a5_data(parse_resource_fork(program))
    pieces = parse_resource_fork(caverns)['PIEC'][3500]['data']

    def words(displacement, count):
        return list(struct.unpack_from(f'>{count}h', data, len(data) + displacement))

    def pointed(table, index):
        return struct.unpack_from('>i', data, len(data) + table + index * 4)[0]

    bubbles = []
    for index in range(6):
        sequence = []
        pointer = pointed(-0x2cfa, index)
        for frame in range(40):
            shape = words(pointer + frame * 2, 1)[0]
            sequence.append(shape)
            if shape == -1:
                break
        else:
            raise ValueError('Unterminated Macintosh lava bubble sequence')
        bubbles.append(sequence)
    limits = words(-0x2e54, 3)
    if limits != [4, 5, 4]:
        raise ValueError('Unsupported Macintosh lava death tables')
    characters = []
    for index, limit in enumerate(limits):
        pointer = pointed(-0x2f4a, index)
        count = limit + 17 if index == 1 else limit + 1
        characters.append([words(pointer + frame * 6, 3) for frame in range(count)])
    return {'schema': 1, 'limits': limits, 'characters': characters, 'bubbles': bubbles,
            'events': [words(-0x2e4e + index * 10, 5) for index in range(22)],
            'splashes': [words(-0x2f5c + frame * 6, 3) for frame in range(3)],
            'piece_offsets': list(struct.unpack_from('>2h', pieces, 0x1d6))}
