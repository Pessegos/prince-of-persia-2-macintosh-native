"""Time-based menu motion, independent of the original game's actor clock."""

from dataclasses import dataclass
import math


def spring_step(position, velocity, target, seconds, *, frequency=24, damping=1):
    seconds = max(0, seconds)
    offset = position - target
    if damping == 1:
        coefficient = velocity + frequency * offset
        decay = math.exp(-frequency * seconds)
        return (target + (offset + coefficient * seconds) * decay,
                (velocity - frequency * coefficient * seconds) * decay)
    decay_rate = damping * frequency
    angular = frequency * math.sqrt(1 - damping * damping)
    coefficient = (velocity + decay_rate * offset) / angular
    cosine, sine = math.cos(angular * seconds), math.sin(angular * seconds)
    decay = math.exp(-decay_rate * seconds)
    return (target + decay * (offset * cosine + coefficient * sine),
            decay * (velocity * cosine - (decay_rate * coefficient + angular * offset) * sine))


@dataclass
class MenuFrameClock:
    """Cap at 120 Hz, with a stable deadline and headroom for slower rendering."""

    deadline: float
    cost: float = 0

    def delay(self, now, rendered_seconds=0):
        self.cost = self.cost * .85 + max(0, rendered_seconds) * .15
        period = max(1 / 120, self.cost * 1.25)
        self.deadline += period
        if self.deadline <= now:
            self.deadline += (math.floor((now - self.deadline) / period) + 1) * period
        return max(1, math.ceil((self.deadline - now) * 1000))
