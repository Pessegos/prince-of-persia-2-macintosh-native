"""GetOppIdxClosestToKid's ordering within an already rebased NPC bank."""

from pop2.terrain import floor_y


def nearest_opponent(player, guards, side=None):
    # CODE 6:36f2-3918 compares absolute Y, not row IDs. At exactly 80
    # pixels of vertical-distance difference, bank order wins.
    best = None
    best_dx = best_dy = 0
    player_y = floor_y(player.row) + player.state.current_y
    for guard in guards:
        living = guard.alive if guard.native_alive is None else guard.native_alive
        if guard.skeleton is not None:
            living = guard.alive or guard.skeleton.native_alive
        ruins = getattr(guard, 'ruins', None)
        if ruins is not None:
            if getattr(ruins, 'removed', False):
                continue
            counter = getattr(ruins, 'dead_frames', None)
            if counter is not None:
                living = counter < 0
            # 6:379e-37a6 excludes heads whose generator mode is flee (2).
            # They must not keep another head waiting on the same side.
            if guard.state.actor_type in (7, 8) and ruins.mode == 2:
                continue
        if not living or guard.room != player.room:
            continue
        delta = guard.state.target_x - player.state.target_x
        if side is not None and (delta > 0 if side < 0 else delta <= 0):
            continue
        dx = abs(delta)
        dy = abs(floor_y(guard.row) + guard.state.current_y - player_y)
        if best is not None and guard.state.actor_type == 11:
            continue
        change_y = abs(dy - best_dy)
        if (best is None or best.state.actor_type == 11
                or change_y > 80 and dy < best_dy
                or change_y < 80 and dx < best_dx):
            best, best_dx, best_dy = guard, dx, dy
    return best
