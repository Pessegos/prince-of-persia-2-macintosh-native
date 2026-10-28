"""Compose recovered sampling, routing and ordinary action input consumption."""

from dataclasses import replace

from tools.reference_input_actions import ActionResult, forward_jump, run, running_jump, step, turn
from tools.reference_input_routes import unarmed_route


def composed_route(bank, pose, *, mode=0, sequence=201, facing_right=True,
                   x=400, warning=1, **terrain):
    bank, requests = unarmed_route(bank, pose, mode=mode, sequence=sequence)
    if not requests:
        return ActionResult(bank, None, x, warning)
    if len(requests) != 1:
        raise NotImplementedError('Draw/target calls are outside composed locomotion')
    name, *arguments = requests[0]
    if name == 'sequence':
        return ActionResult(bank, arguments[0], x, warning)
    if name == 'forward_jump':
        return forward_jump(bank, x=x, warning=warning)
    common = dict(x=x, warning=warning, facing_right=facing_right)
    if name in ('step', 'run'):
        context = {key: terrain[key] for key in ('distance', 'barrier', 'tile_kind') if key in terrain}
        return (step if name == 'step' else run)(bank, **common, **context)
    if name == 'turn':
        context = {key: terrain[key] for key in ('ahead_kind', 'wall', 'wall_distance') if key in terrain}
        return turn(bank, **common, **context)
    if name == 'run_jump':
        context = {key: terrain[key] for key in ('cells', 'gap_distance') if key in terrain}
        return running_jump(bank, pose=pose, sequence=arguments[0], **common, **context)
    raise NotImplementedError(f'Action {name} has not been composed')


def sampled_tick(bank, axes, pose, *, facing_right=True, **context):
    relative = bank.sample(*axes).remap(facing_right=facing_right)
    result = composed_route(relative, pose, facing_right=facing_right, **context)
    return replace(result, bank=result.bank.remap(facing_right=facing_right))
