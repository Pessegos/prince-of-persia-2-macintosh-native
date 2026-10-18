"""Silent, isolated snapshots of the actual playback programs for F3 browsing."""

import random

from PIL import Image, ImageChops, ImageOps, ImageStat

from pop2.development_map import DevelopmentMap
from pop2.paths import ASSET_DIR
from pop2.preview_cache import read_preview, write_preview


GALLERY_SIZE = (488, 278)


def gallery_caption_rect(rect, single=False):
    x1, _y1, x2, y2 = rect
    center = (x1 + x2) // 2
    half_width = 200 if single else 76
    return center - half_width, y2 + 5, center + half_width, y2 + 37


def gallery_caption(font, label, size, color):
    width, height = size
    if not label.strip():
        return Image.new('RGBA', size)
    scale = 1
    lines, line = [], ''
    for word in label.split():
        candidate = f'{line} {word}'.strip()
        if line and font.text(candidate).width * scale > width - 4:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    if len(lines) > 2:
        lines = [lines[0], ' '.join(lines[1:])]
    glyphs = [font.text(line, color) for line in lines]
    scale = min(scale, (width - 4) / max(g.width for g in glyphs))
    line_height = max(1, round((font.height - 1) * scale))
    total = len(lines) * line_height + (len(lines) - 1) * 2
    image = Image.new('RGBA', size)
    for index, glyph in enumerate(glyphs):
        ink = glyph.getbbox()
        if ink is None:
            continue
        glyph = glyph.crop(ink)
        glyph = glyph.resize((max(1, round(glyph.width * scale)),
                              max(1, round(glyph.height * scale))), Image.Resampling.NEAREST)
        image.paste(glyph, ((width - glyph.width) // 2,
                            (height - total) // 2 + index * (line_height + 2)
                            + (line_height - glyph.height) // 2), glyph)
    return image


def gallery_preview(frames, indices):
    image = Image.new('RGB', GALLERY_SIZE, '#101010')
    rooms, sources = {}, {}
    for slot, index in enumerate(indices):
        x, y = 14 + slot % 3 * 164, 2 + slot // 3 * 139
        rect = (94, 2, 394, 228) if len(indices) == 1 else (x, y, x + 132, y + 99)
        rooms[str(index)] = rect
        sources[str(index)] = frames[index]
        image.paste(frames[index].resize((rect[2] - rect[0], rect[3] - rect[1]),
                                         Image.Resampling.LANCZOS), rect[:2])
    return DevelopmentMap(image, rooms, {}, source_frames=sources)


class PlaybackPreviews:
    def __init__(self, resources, parts, attract, fingerprint, directory=ASSET_DIR):
        self.resources, self.parts, self.attract = resources, parts, attract
        self.fingerprint, self.directory = fingerprint, directory
        self.assets, self.frames = {}, {}

    def group(self, indices):
        indices = tuple(indices)
        if indices in self.frames:
            return self.frames[indices]
        path = self.directory / '.developer-cache' / f'playback-{indices[0]}.zip'
        identity = [[self.parts[i].label, self.parts[i].stage, self.parts[i].index] for i in indices]
        cached = read_preview(path, self.fingerprint)
        if cached is not None and cached[0] == identity and set(cached[1]) == {str(i) for i in indices}:
            frames = {i: cached[1][str(i)] for i in indices}
            if all(frame.size == (510, 384) for frame in frames.values()):
                self.frames[indices] = frames
                return frames
        seed = random.getstate()
        try:
            random.seed(17)
            frames = {i: self.snapshot(i) for i in indices}
        finally:
            random.setstate(seed)
        write_preview(path, self.fingerprint, identity, {str(i): frame for i, frame in frames.items()})
        self.frames[indices] = frames
        return frames

    def snapshot(self, index):
        from pop2.intro import IntroAssets, IntroPlayer

        part = self.parts[index]
        if part.stage in ('intro', 'ending'):
            if part.stage not in self.assets:
                self.assets[part.stage] = IntroAssets(self.directory, program_name=f'{part.stage}.json')
            player = IntroPlayer(self.assets[part.stage])
            player.seek_operation(part.index)
            following = next((other.index for other in self.parts[index + 1:]
                              if other.stage == part.stage), len(player.operations))
            if player.title_animation is not None:
                player.advance(6, stop_position=following)
                return player.frame().crop((0, 0, 510, 384)).convert('RGB')
            first_copy = next((i for i in range(part.index, following)
                               if player.operations[i]['op'] in ('copy', 'dissolve')), part.index)
            best = player.frame()
            # Select a visible scene, not a black frame in an intervening fade.
            # The next part is a hard stop, so its imagery cannot leak backward.
            for _ in range(40):
                frame = player.frame()
                stats = ImageStat.Stat(frame.crop((64, 62, 448, 292)).convert('L'))
                if ((part.stage == 'intro' or player.position > first_copy)
                        and stats.stddev[0] > 4 and stats.mean[0] > 3):
                    best = frame
                    break
                if player.done or player.position >= following:
                    break
                player.advance(max(0.001, player.wait_until - player.time), stop_position=following)
            return best.crop((0, 0, 510, 384)).convert('RGB')
        if part.stage == 'credits':
            from pop2.attract import CreditsAssets, CreditsPlayer

            if 'credits' not in self.assets:
                self.assets['credits'] = CreditsAssets(self.attract, self.directory)
            player = CreditsPlayer(self.assets['credits'])
            player.seek_page(part.index)
            player.advance(self.assets['credits'].program['dissolve_ticks'] / 60.14742)
            return player.frame().crop((0, 0, 510, 384)).convert('RGB')
        return self.room_snapshot(part)

    def room_snapshot(self, part):
        from pop2.attract import actor_state
        from pop2.combat_art import GuardArtwork, sword_palette_for_level
        from pop2.harbor import Harbor
        from pop2.level_rendering import LevelRenderer
        from pop2.render_opening import (character_sprite_top, decode_shap, kid_palette_for_level,
                                        load_resource_file)
        from pop2.animation_data import shape_id_for_action
        from pop2.sequence_runtime import SequenceState
        from pop2.terrain import floor_y

        number = 1 if part.stage == 'demo' else part.index
        key = f'level-{number}'
        if key not in self.assets:
            self.assets[key] = LevelRenderer(self.resources.level(number), preload_room=False)
        renderer = self.assets[key]
        if part.stage == 'demo':
            recording = self.attract['frames']
            sample = part.index
            while sample < min(part.index + 8, len(recording) - 1):
                if recording[sample + 1]['room'] != recording[part.index]['room']:
                    break
                sample += 1
            frame = recording[sample]
            room = frame['room'] - 1
            words = frame['actors'][5]
            state, row = actor_state(words, 0), words[7]
        else:
            level = self.resources.level(number)
            room, row = level.start_room, level.start_row
            state = SequenceState(5, action=15, target_x=level.start_x, facing=level.facing,
                                  actor_type=0, level_kind=level.kind)
        art = renderer.room(room)
        harbor = Harbor() if number == 1 else None
        image = renderer.animated_layer(art.background.copy(), room, harbor)
        image = Image.alpha_composite(image, art.foreground)
        if part.stage == 'demo':
            key = 'guard'
            if key not in self.assets:
                self.assets[key] = GuardArtwork(load_resource_file('Guard.rsrc'),
                    self.resources.prince['SHAP'],
                    int.from_bytes(self.resources.prince['SHPL'][1000]['data'][:2], 'big'),
                    sword_palette_for_level(self.resources.prince, 5))
            guards = self.assets[key]
            for words in frame['actors'][:5]:
                if words[1] in (0, -1) and words[11] - 1 == room:
                    actor = actor_state(words, 2)
                    layer = Image.new('RGBA', image.size)
                    guards.draw(layer, actor, floor_y(words[7]))
                    layer.putalpha(ImageChops.multiply(layer.getchannel('A'),
                                                       ImageChops.invert(art.foreground.getchannel('A'))))
                    image = Image.alpha_composite(image, layer)
        record = self.resources.frames[state.action]
        shape = shape_id_for_action(self.resources.frames, self.resources.first_shape_id, state.action)
        if shape is not None:
            palette = kid_palette_for_level(self.resources.kid, self.resources.level(number).kind)
            body = decode_shap(self.resources.kid['SHAP'][shape]['data'], palette)
            if state.facing:
                body = ImageOps.mirror(body)
            x = state.target_x - (body.width - record.offset_x if state.facing else record.offset_x)
            y = character_sprite_top(floor_y(row) + state.current_y + record.offset_y, body.height)
            layer = Image.new('RGBA', image.size)
            layer.paste(body, (x, y), body)
            kind, sword_index, dx, dy = self.resources.attachment_frames[record.afrm_index]
            if kind == 1 and sword_index >= 0:
                base = int.from_bytes(self.resources.prince['SHPL'][1000]['data'][:2], 'big')
                sword = decode_shap(self.resources.prince['SHAP'][base + sword_index]['data'],
                                    sword_palette_for_level(self.resources.prince, state.level_kind))
                if state.facing:
                    sword = ImageOps.mirror(sword)
                sx = x + body.width + dx - sword.width if state.facing else x - dx
                layer.paste(sword, (sx, y + body.height + dy - sword.height), sword)
            bounds = x, y, x + body.width - 1, y + body.height - 1
            mask = art.actor_mask(row, bounds[3], state, bounds, record)
            layer.putalpha(ImageChops.multiply(layer.getchannel('A'), ImageChops.invert(mask)))
            image = Image.alpha_composite(image, layer)
        image = renderer.animated_layer(image, room, harbor, front=True)
        result = Image.new('RGB', (510, 384))
        result.paste(image.crop((0, 0, 510, 360)), (0, 0))
        return result
