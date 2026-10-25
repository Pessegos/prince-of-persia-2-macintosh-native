"""Ephemeral attribution for mixing native gate cues by motion direction."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GateSound:
    cue: int | None
    opening: bool
    source: tuple[int, int]


@dataclass
class GateVoice:
    gate_tail: object
    effect_channel: int
    tail_channel: int
