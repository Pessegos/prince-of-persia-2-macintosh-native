from dataclasses import dataclass, field


HARBOR_ROOMS = {14, 15, 18}
WATER_ROOMS = {15, 18}
SHIP_ROOM = 18
SHIP_CLIMB_SEQUENCE = 59


@dataclass
class WaterEntry:
    room: int
    x: int
    tumble: bool
    age: int = 0


@dataclass
class Harbor:
    """Mutable rooftop objects from CODE:23, separate from the level resource."""

    ship_frame: int = 0
    ship_active: bool = False
    wave_frame: int = 0
    water: dict[int, WaterEntry] = field(default_factory=dict)

    def enter_room(self, room, action):
        # PrepCut -> KeepTime -> TriggerRoofShip (2:5374 / 23:1256).
        if room == SHIP_ROOM and self.ship_frame < 98:
            if 34 <= action <= 40:
                self.ship_frame = 6
            self.ship_active = True

    def advance(self):
        self.wave_frame = (self.wave_frame + 1) & 3
        for entry in self.water.values():
            entry.age += 1
        if self.ship_active:
            self.ship_frame += 1
            if self.ship_frame > 98:
                self.ship_active = False

    @property
    def ship_x(self):
        return -2 * self.ship_frame

    def can_grab_ship(self, room, row, x):
        # RoofCanGrabShip 23:12f0: native X = scene X + 207.
        return room == SHIP_ROOM and row < 3 and x < 90 and self.ship_frame < 33

    @staticmethod
    def hanging_from_ship(room, state):
        return (room == SHIP_ROOM and state.target_x < 90
                and (state.animation_state in (2, 6) or state.action == 80))

    @staticmethod
    def right_exit_is_fatal(room, state):
        # RoofMakeWaterTestRect 23:0882: native X >818, scene X >611.
        return room == 14 and state.level_kind == 5 and state.target_x > 611

    def watch_water(self, actor_id, room, row, state, width=0):
        # RoofWatchOpps / 23:06fe. Exempt the native catch/climb sequences.
        entry = self.water.get(actor_id)
        if entry is None:
            if (room not in WATER_ROOMS or state.sequence_id in (68, 15, 59, 10)
                    or state.animation_state == 2):
                return False
            threshold = 354 if state.animation_state == 9 else 327
            if row * 120 + 106 + state.current_y < threshold:
                return False
            x = state.target_x + (width // 2) * (-1 if state.facing else 1)
            self.water[actor_id] = WaterEntry(room, x, state.animation_state == 9)
            state.sound_events.append(35)
            return False
        return entry.age > 7 and row >= 2
