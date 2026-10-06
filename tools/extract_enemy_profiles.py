"""Recover AI globals and enemy generators from the unmodified Mac resources."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from pop2.paths import ASSET_DIR


TABLE_OFFSETS = {
    "advance": -0x3638,
    "block": -0x3668,
    "parry_block": -0x3650,
    "counter": -0x3680,
    "strike": -0x3698,
    "hit_pause": -0x36BA,
}


def expand_a5_data(resources):
    # CODE:1 0x00da: every zero DATA word consumes one ZERO byte-run length.
    data = resources["DATA"][0]["data"]
    zero = resources["ZERO"][0]["data"]
    size = struct.unpack_from(">I", resources["CODE"][0]["data"], 4)[0]
    if len(data) % 2 or len(zero) % 2:
        raise ValueError("Odd-sized DATA/ZERO resource")
    output = bytearray()
    cursor = 0
    for offset in range(0, len(data), 2):
        word = data[offset : offset + 2]
        output.extend(word)
        if word == b"\0\0":
            count = struct.unpack_from(">H", zero, cursor)[0]
            output.extend(bytes(count))
            cursor += 2
        if len(output) > size:
            raise ValueError("DATA expansion exceeds the CODE:0 A5 allocation")
    if len(output) != size or cursor != len(zero):
        raise ValueError("DATA/ZERO lengths disagree with CODE:0")
    return bytes(output)


def extract(program_path, prince_path):
    return extract_bytes(program_path.read_bytes(), prince_path.read_bytes())


def extract_bytes(program_bytes, prince_bytes):
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork(prince_bytes)
    a5 = expand_a5_data(program)
    tables = {
        name: struct.unpack_from(">12H", a5, len(a5) + offset)
        for name, offset in TABLE_OFFSETS.items()
    }
    profiles = [
        {"skill": i, **{name: values[i] for name, values in tables.items()}}
        for i in range(12)
    ]
    # GenerateOpponent 0x3b16-0x3b56: separate entry anchors on each side.
    generation_x = [
        struct.unpack_from(
            ">h", a5, len(a5) + (-0x4B8C if column <= 5 else -0x4B84) + column * 2
        )[0]
        for column in range(10)
    ]
    levels = []
    for resource_id, resource in sorted(prince["LEVL"].items()):
        if not 2000 <= resource_id <= 2013:
            continue
        level = resource["data"]
        opponent_set = struct.unpack_from(">h", level, 0x21A4)[0]
        actor_type = struct.unpack_from(">h", a5, len(a5) - 0x5280 + opponent_set * 2)[
            0
        ]
        generators = []
        for room in range(1, 25):
            start = 0x20E6 + room * 0xC0
            count = struct.unpack_from(">H", level, start)[0]
            if count > 5:
                raise ValueError(
                    f"LEVL:{resource_id}, room {room}: invalid generator count"
                )
            for index in range(count):
                offset = start + 2 + index * 38
                fields = struct.unpack_from(">19h", level, offset)
                if not 0 <= fields[3] < 12:
                    raise ValueError(f"Unsupported skill {fields[3]}")
                # InitOpps, CODE:6 0x2bd2-0x2c0e, preserves special overrides.
                kind = fields[12]
                if opponent_set not in (5, 6) and kind not in (1, 9, 10, 3):
                    kind = opponent_set
                initial_type = struct.unpack_from(
                    ">h", a5, len(a5) - 0x5280 + kind * 2
                )[0]
                generators.append(
                    {
                        "room": room,
                        "index": index,
                        "offset": f"0x{offset:04x}",
                        "tile": fields[0],
                        "row": fields[0] // 10,
                        "native_x": fields[1],
                        "scene_x": fields[1] - 207,
                        "native_facing": fields[2],
                        "skill": fields[3],
                        "initial_sequence": fields[4],
                        "max_life_field": fields[13],
                        "max_life_defaulted": fields[13] or 3,
                        "initial_opponent_kind": kind,
                        "initial_actor_type": initial_type,
                        "raw_words": list(fields),
                    }
                )
        generation_points = []
        for room in range(1, 25):
            start = 0x3986 + room * 0x44
            count, skill = struct.unpack_from(">2h", level, start)
            if not 0 <= count <= 3:
                raise ValueError(
                    f"LEVL:{resource_id}, room {room}: invalid generation points"
                )
            for index in range(count):
                offset = start + 8 + index * 20
                fields = struct.unpack_from(">10h", level, offset)
                generation_points.append(
                    {
                        "room": room,
                        "index": index,
                        "offset": f"0x{offset:04x}",
                        "skill": skill,
                        "row": fields[2],
                        "column": fields[3],
                        "initial_wait": fields[4],
                        "repeat_wait": fields[5],
                        "remaining": fields[8],
                        "life_word": fields[9],
                        "raw_words": list(fields),
                    }
                )
        levels.append(
            {
                "resource_id": resource_id,
                "level_index": resource_id - 2000,
                "opponent_set": opponent_set,
                "initial_actor_type": actor_type,
                "generators": generators,
                "generation_points": generation_points,
            }
        )
    return {
        "schema": 1,
        "sources": {
            "program_sha256": hashlib.sha256(program_bytes).hexdigest(),
            "prince_sha256": hashlib.sha256(prince_bytes).hexdigest(),
            "a5_size": len(a5),
            "table_a5_offsets": {
                name: f"-{abs(offset):#x}" for name, offset in TABLE_OFFSETS.items()
            },
        },
        "random_limit_inclusive": 255,
        "generation_native_x": generation_x,
        "profiles": profiles,
        "levels": levels,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", type=Path, help="Original application resource fork")
    parser.add_argument("prince", type=Path, help="Original Prince.rsrc resource fork")
    parser.add_argument(
        "--output", type=Path, default=ASSET_DIR / "enemy_profiles.json"
    )
    args = parser.parse_args()
    result = extract(args.program, args.prince)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="ascii")
    count = sum(len(level["generators"]) for level in result["levels"])
    points = sum(len(level["generation_points"]) for level in result["levels"])
    print(
        f"Recovered {len(result['profiles'])} profiles, {count} initial generators "
        f"and {points} reinforcement points "
        f"in {len(result['levels'])} levels: {args.output}"
    )


if __name__ == "__main__":
    main()
