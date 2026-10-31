"""Original guard rendering, damage bursts and the game's health-bottle HUD."""

import struct
from dataclasses import replace

from PIL import ImageOps

from pop2.animation_data import (
    character_collision_bounds, parse_aframe_records, parse_frame_records, shape_id_for_action,
)
from pop2.render_opening import (
    ROOM_ORIGIN_X, actor_foreground_column, character_sprite_top, decode_ctbl, decode_shap,
)
from pop2.terrain import character_row


def sword_palette_for_level(prince, level_kind):
    colors = decode_ctbl(prince['CTBL'][1000 + level_kind]['data'])
    palette = {239 + index: color for index, color in colors.items()}
    # A few sword SHAPs use index 250, absent from CTBL:1005.
    palette[250] = (150, 69, 0, 255)
    return palette


FLAME_SWORD_FILE = 'FlameSword.rsrc'


def opponent_artwork(level, sword_shapes, sword_base, sword_palette, artwork=None):
    """The level's ordinary opponent artwork, plus level twelve's flaming
    sword (opponent set 1, 3:5f58) when FlameSword.rsrc is imported."""
    from pop2.render_opening import load_resource_file

    default = GuardArtwork(load_resource_file(artwork or guard_artwork_file(level)),
                           sword_shapes, sword_base, sword_palette)
    flame = None
    if struct.unpack_from('>h', level.data, 0x21a4)[0] == 7:
        try:
            flame = FlameSwordArtwork(load_resource_file(FLAME_SWORD_FILE))
        except (FileNotFoundError, KeyError):
            flame = None
    return OpponentArtwork(default, flame)


def guard_artwork_file(level):
    """The ordinary opponents' file by LEVL opponent set (0x21a4; 3:5f58):
    the caverns' skeletons, the temple's birdheads (set 7), else guards."""
    if struct.unpack_from('>h', level.data, 0x21a4)[0] == 7:
        return 'Birdhead.rsrc'
    return 'Skeleton.rsrc' if level.kind == 3 else 'Guard.rsrc'


def actor_draw_order(state, record, bounds, row):
    """IndexChar/DrawObjs/CompareObj ordering for Prince and ordinary opponents."""
    if state.animation_state == 1:
        row = character_row(bounds[3])
        if row == -1:
            row = 3
    column = actor_foreground_column(state, record, bounds)
    # IndexCell1 assigns offscreen actors to bucket 30, visited first.
    # Visible cells follow bottom-up, left-right. Ordinary character kinds
    # share priority 127 and sort by shape bottom, then anchor within a cell.
    cell = 1 + (2 - row) * 10 + column if 0 <= row < 3 and 0 <= column < 10 else 0
    anchor = bounds[2] + 1 if state.facing else bounds[0]
    return cell, bounds[3], anchor


def slab_crush_draw_state(actor, previous_poses):
    """Keep the pre-impact expression during the head crush's first frame.

    SEQS146 really starts with resting pose150. Only its displayed pose is
    replaced; the native sequence cursor, motion and death timing stay intact.
    The scene discards these presentation snapshots at the next frame start.
    """
    state = actor.state
    previous = previous_poses.get(id(actor))
    if (previous is not None and previous[0] is actor and state.actor_type in (7, 8)
            and state.sequence_id == state.source_sequence_id == 146
            and state.cursor == 1 and state.action == 150):
        return replace(state, action=previous[1])
    return state


class GuardArtwork:
    def __init__(self, resource, sword_shapes, sword_base, sword_palette):
        self.shapes = resource["SHAP"]
        self.base = int.from_bytes(resource["SHPL"][750]["data"][:2], "big")
        self.frames = parse_frame_records(resource["FRAM"][750]["data"])
        self.attachments = parse_aframe_records(resource["AFRM"][750]["data"])
        # InitOpps generator +0x0c, then CODE:6 0x4210: CTBL = 749 + variant.
        self.palettes = {key - 749: decode_ctbl(value["data"])
                         for key, value in resource["CTBL"].items()}
        self.sword_shapes = sword_shapes
        self.sword_base = sword_base
        self.sword_palette = sword_palette
        self.cache = {}
        self.sword_cache = {}

    def body(self, state, palette_variant=1):
        from pop2.combat import actor_frame_index

        index = actor_frame_index(state)
        shape_id = shape_id_for_action(self.frames, self.base, index)
        if shape_id is None:
            return None
        shapes, palette = self.shapes, self.palettes[palette_variant]
        if state.actor_type == 4 and 206 <= state.action <= 209:
            # SetupSword 3:0b76-0b98 switches bones to environment bank 4,
            # adding 109 to the FRAM shape index, not to the skeleton bank.
            from pop2.caverns import cavern_assets
            _, resources, palette, _ = cavern_assets()
            base = int.from_bytes(resources['SHPL'][3500]['data'][:2], 'big')
            shape_id = base + 109 + self.frames[index].shape_index
            shapes = resources['SHAP']
        key = (shape_id, palette_variant)
        if key not in self.cache:
            self.cache[key] = decode_shap(shapes[shape_id]['data'], palette)
        return self.cache[key]

    def draw(self, image, state, floor_y, palette_variant=1):
        from pop2.combat import actor_frame_index

        if state.actor_type == 4 and state.source_sequence_id == 115:
            return  # The lava pool draws the sinking skeleton, CODE:8 34a6.
        index = actor_frame_index(state)
        body = self.body(state, palette_variant)
        if body is None:
            return
        record = self.frames[index]
        anchor = record.offset_x
        if state.facing:
            body = ImageOps.mirror(body)
            anchor = body.width - anchor
        x = state.target_x - anchor
        y = character_sprite_top(floor_y + state.current_y + record.offset_y, body.height)
        image.paste(body, (x, y), body)
        kind, sword_index, dx, dy = self.attachments[record.afrm_index]
        if kind != 1 or sword_index < 0:
            return
        sword_id = self.sword_base + sword_index
        if sword_id not in self.sword_cache:
            self.sword_cache[sword_id] = decode_shap(
                self.sword_shapes[sword_id]["data"], self.sword_palette)
        sword = self.sword_cache[sword_id]
        if state.facing:
            sword = ImageOps.mirror(sword)
            sword_x = x + body.width + dx - sword.width
        else:
            sword_x = x - dx
        image.paste(sword, (sword_x, y + body.height + dy - sword.height), sword)

    def bounds(self, state, floor_y):
        from pop2.combat import actor_frame_index

        index = actor_frame_index(state)
        body = self.body(state)
        if body is None:
            return (state.target_x, floor_y, state.target_x, floor_y)
        record = self.frames[index]
        anchor = body.width - record.offset_x if state.facing else record.offset_x
        left = state.target_x - anchor
        bottom = floor_y + state.current_y + record.offset_y
        return (left, character_sprite_top(bottom, body.height),
                left + body.width - 1, bottom)

    def collision_bounds(self, state, floor_y, sword_drawn):
        from pop2.combat import actor_frame_index

        record = self.frames[actor_frame_index(state)]
        return character_collision_bounds(state, self.bounds(state, floor_y),
                                          self.attachments[record.afrm_index], sword_drawn)


class FlameSwordArtwork(GuardArtwork):
    """FlameSword.rsrc: no body, only the AFRM piece in its own SHAP bank
    (SetupSword 3:0b16-0b2a, image set 3) at AddFCharX of the piece's X."""

    def __init__(self, resource):
        self.shapes = resource["SHAP"]
        self.base = int.from_bytes(resource["SHPL"][750]["data"][:2], "big")
        self.frames = parse_frame_records(resource["FRAM"][750]["data"])
        self.attachments = parse_aframe_records(resource["AFRM"][750]["data"])
        self.palette = decode_ctbl(resource["CTBL"][750]["data"])
        self.cache = {}

    def body(self, state, palette_variant=1):
        return None

    def placement(self, state, floor_y, piece=None):
        from pop2.combat import actor_frame_index

        record = self.frames[actor_frame_index(state)]
        kind, shape, dx, dy = self.attachments[record.afrm_index]
        piece = shape if piece is None else piece
        if piece < 0 or kind != 1:
            return None
        if piece not in self.cache:
            image = decode_shap(self.shapes[self.base + piece]["data"], self.palette)
            self.cache[piece] = (image, ImageOps.mirror(image))
        image, mirrored = self.cache[piece]
        # Native X = X +/- (FRAM X + AFRM X), Y = Y + FRAM Y + AFRM Y, with
        # the same edge rule as an attached guard sword.
        offset = record.offset_x + dx
        bottom = floor_y + state.current_y + record.offset_y + dy
        if state.facing:
            return mirrored, state.target_x + offset - mirrored.width, bottom
        return image, state.target_x - offset, bottom

    def draw(self, image, state, floor_y, palette_variant=1, piece=None):
        placed = self.placement(state, floor_y, piece)
        if placed is None:
            return
        sprite, x, bottom = placed
        image.paste(sprite, (x, character_sprite_top(bottom, sprite.height)), sprite)

    def bounds(self, state, floor_y, piece=None):
        placed = self.placement(state, floor_y, piece)
        if placed is None:
            return (state.target_x, floor_y, state.target_x, floor_y)
        sprite, x, bottom = placed
        return (x, character_sprite_top(bottom, sprite.height), x + sprite.width - 1, bottom)

    def collision_bounds(self, state, floor_y, sword_drawn):
        return self.bounds(state, floor_y)


class OpponentArtwork:
    """The loaded opponent set (a5-0x46dc, CheckLoadedOppSet 3:5278). Frame
    records follow the set loaded for the Prince's room; each actor is drawn
    with its own file (the port does not reproduce mismatched side rooms)."""

    def __init__(self, default, flame=None):
        self.default, self.flame = default, flame
        self.current = default

    def select_room(self, actors):
        self.current = (self.flame if self.flame is not None
                        and any(actor.state.actor_type == 10 for actor in actors) else self.default)

    def _art(self, state):
        return self.flame if state.actor_type == 10 and self.flame is not None else self.default

    @property
    def frames(self):
        return self.current.frames

    @property
    def base(self):
        return self.current.base

    @property
    def attachments(self):
        return self.current.attachments

    def body(self, state, palette_variant=1):
        return self._art(state).body(state, palette_variant)

    def draw(self, image, state, floor_y, palette_variant=1, piece=None):
        art = self._art(state)
        if state.actor_type == 10 and art is not self.flame:
            return  # FlameSword.rsrc is not imported.
        if art is self.flame:
            art.draw(image, state, floor_y, palette_variant, piece)
        else:
            art.draw(image, state, floor_y, palette_variant)

    def bounds(self, state, floor_y, piece=None):
        art = self._art(state)
        return art.bounds(state, floor_y, piece) if art is self.flame else art.bounds(state, floor_y)

    def collision_bounds(self, state, floor_y, sword_drawn):
        return self._art(state).collision_bounds(state, floor_y, sword_drawn)


class _CurrentFrames:
    def __init__(self, artwork):
        self.artwork = artwork

    def __getitem__(self, index):
        return self.artwork.frames[index]

    def __len__(self):
        return len(self.artwork.frames)


class HealthArtwork:
    def __init__(self, kid, palette, base):
        # DrawKidMeter/DrawOppMeter: shape indices 300/299 and 298/297.
        self.icons = {
            index: decode_shap(kid["SHAP"][base + index]["data"], palette)
            for index in range(297, 301)
        }

    def draw(self, viewport, encounter, show_opponent=True, *, player_life=None):
        life = encounter.player.life if player_life is None else player_life
        for index in range(encounter.player.max_life):
            full = index < life
            # CODE:2 5442-546c redraws only the final life, on the world clock.
            if index == 0 and life == 1:
                full = bool(encounter.world_frame & 1)
            icon = self.icons[300 if full else 299]
            # DrawKidMeter coordinates belong to the visible 510-pixel game,
            # which is centered inside the host's 512-pixel composition buffer.
            viewport.paste(icon, (ROOM_ORIGIN_X + 3 + index * 12, 368), icon)
        opponent = encounter.health_opponent() if show_opponent else None
        if opponent is not None:
            # DrawOppMeter draws current life only, unlike DrawKidMeter.
            # Heads store half-bottle points (3:4bc8-4bea/4c3a-4c60).
            heads = opponent.state.actor_type in (7, 8)
            full, half = divmod(opponent.life, 2) if heads else (opponent.life, 0)
            for index in range(full + half):
                icon = self.icons[298 if index < full else 297]
                viewport.paste(icon, (ROOM_ORIGIN_X + 495 - index * 12, 368), icon)


class HitArtwork:
    def __init__(self, kid, palette, base, player_frames, guard_frames):
        # CODE:3 0x0bbc uses Kid shape index 218, not a rooftop water splash.
        self.sprite = decode_shap(kid["SHAP"][base + 218]["data"], palette)
        self.mirrored = ImageOps.mirror(self.sprite)
        self.player_frames = player_frames
        self.guard_frames = guard_frames

    def draw(self, image, state, floor_y):
        from pop2.combat import actor_frame_index

        # SetupChar 0x07dc consumes state 10 on the first hurt/death pose.
        # Keep rendering that pose until its next animation tick, not per paint.
        # SetupOpp 3:0994-09ce also draws the first mode-9 tumble pose.
        tumble_hit = state.actor_type == 2 and state.animation_state == 9 and state.action == 213
        if state.animation_state != 10 and not tumble_hit and not state.hit_flash:
            return
        is_player = state.actor_type == 0
        record = (self.player_frames[state.action] if is_player
                  else self.guard_frames[actor_frame_index(state)])
        # 0x0ca4/0x0cb6 offset from the body's facing-relative draw anchor.
        dx, dy = (14, -30) if is_player else (11, -21)
        sprite = self.mirrored if state.facing else self.sprite
        anchor = record.offset_x + dx
        x = (state.target_x + anchor - sprite.width if state.facing
             else state.target_x - anchor)
        bottom = floor_y + state.current_y + record.offset_y + dy
        image.paste(sprite, (x, character_sprite_top(bottom, sprite.height)), sprite)
