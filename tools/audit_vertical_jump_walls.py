"""Audit stored wall-adjacent standing fixtures against widening vertical poses.

This exercises the port. It does not execute the original Macintosh code or
prove that every supplied position is reachable from the campaign entrance.
"""
import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def audit():
    from pop2.terrain import EMPTY_TILES, WALL_TILES, character_column, floor_contact_x
    from tools.audit_temple_routes import Harness, press

    harness = Harness(12, peaceful=True)
    scene = harness.scene
    candidates = set()
    fixtures = poses = 0
    try:
        for level in range(1, 15):
            scene.load_level(level)
            for room in range(32):
                for row in range(3):
                    scene.terrain_motion.row = row
                    for col in range(10):
                        if scene.level_map.tile(room, col, row).kind not in WALL_TILES - {43}:
                            continue
                        for facing, x in ((0, col * 51 + 11), (1, col * 51 + 86)):
                            if not 0 <= x < 510:
                                continue
                            state = scene.sequence_state
                            state.action, state.facing = 15, facing
                            state.current_x = state.target_x = x
                            state.current_y = 0
                            contact = floor_contact_x(x, facing, scene.frames[15])
                            cell = scene.level_map.tile(room, character_column(contact), row)
                            if cell.kind in EMPTY_TILES | WALL_TILES:
                                continue
                            old = scene.player_collision_bounds()
                            fixtures += 1
                            for pose in range(67, 80):
                                state.action = pose
                                bounds = scene.player_collision_bounds()
                                raw = scene.level_map.wall_correction(
                                    room, x, x, bounds, old, facing, physical_row=row, state=state)
                                poses += 1
                                if raw == x:
                                    continue
                                shift = raw - x
                                translated = (old[0] + shift, old[1], old[2] + shift, old[3])
                                safe = scene.level_map.tile_correction(
                                    room, shift, raw, translated, old, None, row, state,
                                    solid_only=True)
                                if raw != safe:
                                    candidates.add((level, room, row, facing, x))
    finally:
        harness.close()
    results = []
    for level, room, row, facing, x in sorted(candidates):
        harness = Harness(level, peaceful=True)
        try:
            scene = harness.scene
            scene.jump_to_room(room, row=row, x=x, facing=facing, redraw=False)
            state = scene.sequence_state
            record = scene.frames[state.action]
            ledge = (scene.level_map.upper_ledge(room, row, state, record) is not None
                     or scene.level_map.back_ledge_jump(room, row, state, record) is not None)
            corrections = []
            original = scene.level_map.tile_correction

            def track(*args, **kwargs):
                result = original(*args, **kwargs)
                if kwargs.get('solid_only') and result != args[2]:
                    corrections.append((args[2], result))
                return result

            scene.level_map.tile_correction = track
            press(harness, 'up', True)
            path = []
            for _ in range(20):
                harness.tick()
                path.append((scene.room_id + 1, state.target_x, state.action))
            if corrections and not ledge and any(
                    r != room + 1 or abs(px - x) > 12 for r, px, _pose in path):
                raise AssertionError((level, room + 1, row, facing, x, path))
            results.append(dict(level=level, room=room + 1, row=row, facing=facing,
                                x=x, ledge_jump=ledge, guarded_corrections=corrections, path=path))
        finally:
            harness.close()
    return dict(levels=list(range(1, 15)), standing_fixtures=fixtures, pose_fixtures=poses,
                candidates=results, exclusions=[
                    'Supplied idle placements beside stored wall cells, initial level mechanism phases',
                    'Vertical pose shapes tested at standing Y; candidate does not imply a reachable jump',
                    'Real-key replay of candidates only; peaceful mode excludes opponent control',
                    'No native CPU probe, physical desktop, full campaign reachability or all animation states'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix='pop2-vertical-audit-') as user_data:
        with patch.dict(os.environ, {'POP2_USER_DATA': user_data}):
            result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"{result['standing_fixtures']} standing fixtures; "
          f"{len(result['candidates'])} candidate locations replayed")


if __name__ == '__main__':
    main()
