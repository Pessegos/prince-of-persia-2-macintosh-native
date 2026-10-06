"""Original guard rendering, damage bursts and the game's health-bottle HUD."""

from PIL import ImageOps

from pop2.animation_data import parse_aframe_records, parse_frame_records, shape_id_for_action
from pop2.combat import guard_frame_index
from pop2.render_opening import character_sprite_top, decode_ctbl, decode_shap


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

    def draw(self, image, state, floor_y, palette_variant=1):
        index = guard_frame_index(state.action)
        shape_id = shape_id_for_action(self.frames, self.base, index)
        if shape_id is None:
            return
        key = (shape_id, palette_variant)
        if key not in self.cache:
            self.cache[key] = decode_shap(
                self.shapes[shape_id]["data"], self.palettes[palette_variant])
        body = self.cache[key]
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
        index = guard_frame_index(state.action)
        shape_id = shape_id_for_action(self.frames, self.base, index)
        if shape_id is None:
            return (state.target_x, floor_y, state.target_x, floor_y)
        key = (shape_id, 1)
        if key not in self.cache:
            self.cache[key] = decode_shap(self.shapes[shape_id]["data"], self.palettes[1])
        body, record = self.cache[key], self.frames[index]
        anchor = body.width - record.offset_x if state.facing else record.offset_x
        left = state.target_x - anchor
        bottom = floor_y + state.current_y + record.offset_y
        return (left, character_sprite_top(bottom, body.height),
                left + body.width - 1, bottom)


class HealthArtwork:
    def __init__(self, kid, palette, base):
        # DrawKidMeter/DrawOppMeter: shape indices 300/299 and 298/297.
        self.icons = {
            index: decode_shap(kid["SHAP"][base + index]["data"], palette)
            for index in range(297, 301)
        }

    def draw(self, viewport, encounter, show_opponent=True):
        for index in range(encounter.player.max_life):
            full = index < encounter.player.life
            # CODE:2 5442-546c redraws only the final life, on the world clock.
            if index == 0 and encounter.player.life == 1:
                full = bool(encounter.world_frame & 1)
            icon = self.icons[300 if full else 299]
            viewport.paste(icon, (3 + index * 12, 368), icon)
        if (show_opponent and encounter.guard is not None and encounter.guard.alive
                and encounter.guard.room == encounter.player.room
                and encounter.guard.row == encounter.player.row):
            for index in range(encounter.guard.max_life):
                icon = self.icons[298 if index < encounter.guard.life else 297]
                viewport.paste(icon, (495 - index * 12, 368), icon)


class HitArtwork:
    def __init__(self, kid, palette, base, player_frames, guard_frames):
        # CODE:3 0x0bbc uses Kid shape index 218, not a rooftop water splash.
        self.sprite = decode_shap(kid["SHAP"][base + 218]["data"], palette)
        self.mirrored = ImageOps.mirror(self.sprite)
        self.player_frames = player_frames
        self.guard_frames = guard_frames

    def draw(self, image, state, floor_y):
        # SetupChar 0x07dc consumes state 10 on the first hurt/death pose.
        # Keep rendering that pose until its next animation tick, not per paint.
        if state.animation_state != 10:
            return
        is_player = state.actor_type == 0
        record = (self.player_frames[state.action] if is_player
                  else self.guard_frames[guard_frame_index(state.action)])
        # 0x0ca4/0x0cb6 offset from the body's facing-relative draw anchor.
        dx, dy = (14, -30) if is_player else (11, -21)
        sprite = self.mirrored if state.facing else self.sprite
        anchor = record.offset_x + dx
        x = (state.target_x + anchor - sprite.width if state.facing
             else state.target_x - anchor)
        bottom = floor_y + state.current_y + record.offset_y + dy
        image.paste(sprite, (x, character_sprite_top(bottom, sprite.height)), sprite)
