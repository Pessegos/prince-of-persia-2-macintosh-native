"""AI constants recovered by extract_enemy_profiles.py."""

from dataclasses import dataclass
import json
from pathlib import Path
import random


ENEMY_DATA = json.loads((Path(__file__).parent / "assets" /
                        "enemy_profiles.json").read_text(encoding="ascii"))


@dataclass(frozen=True)
class EnemyProfile:
    skill: int
    advance: int
    block: int
    parry_block: int
    counter: int
    strike: int
    hit_pause: int


PROFILES = tuple(EnemyProfile(**profile) for profile in ENEMY_DATA["profiles"])
ADVANCE_CHANCE = tuple(p.advance for p in PROFILES)
BLOCK_CHANCE = tuple(p.block for p in PROFILES)
PARRY_BLOCK_CHANCE = tuple(p.parry_block for p in PROFILES)
COUNTER_CHANCE = tuple(p.counter for p in PROFILES)
STRIKE_CHANCE = tuple(p.strike for p in PROFILES)
HIT_PAUSE = tuple(p.hit_pause for p in PROFILES)


class QuickDrawRandom:
    """Mac II ROM 0x1d7ec and PoP2 Rnd (CODE:17 0x6e06)."""

    MODULUS = 0x7FFFFFFF

    def __init__(self, seed=None):
        if seed is None:
            seed = random.SystemRandom().randrange(1, self.MODULUS)
        if not 0 < seed < self.MODULUS:
            raise ValueError("QuickDraw seed must be between 1 and 2147483646")
        self.seed = seed

    def randrange(self, stop):
        if stop <= 0:
            raise ValueError("Random range must be positive")
        self.seed = self.seed * 16807 % self.MODULUS
        word = self.seed & 0xFFFF
        # ROM 0x1d830 excludes the signed value -32768.
        if word == 0x8000:
            word = 0
        return word % stop
