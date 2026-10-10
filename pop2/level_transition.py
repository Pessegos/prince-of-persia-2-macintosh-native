"""The level-exit music gate used before CheckPlayNIS (2:6134-6168)."""

from dataclasses import dataclass


@dataclass
class LevelExit:
    song: int
    duration: float
    elapsed: float = 0

    def advance(self, seconds, audio=None):
        self.elapsed += max(0, seconds)
        if audio is not None and audio.available(self.song):
            return (audio.current_music == self.song and not audio.music_busy
                    and audio.death_ready())
        return self.elapsed >= self.duration
