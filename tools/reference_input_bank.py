"""Executable research model of the Macintosh input bank, not a host queue."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class InputBank:
    left: int = 0
    right: int = 0
    up: int = 0
    down: int = 0
    modifier: int = 0

    def sample(self, horizontal=0, vertical=0, modifier=0):
        """4:3e84-3f42, after ReadKeyboard's raw-axis priorities."""
        if horizontal not in (-1, 0, 1) or vertical not in (-1, 0, 1):
            raise ValueError('Invalid raw direction')
        if modifier not in (-2, -1, 0):
            raise ValueError('Invalid raw modifier')

        def direction(old, pressed):
            if old < 0:
                return old
            if not pressed:
                return 0
            return -1 if old == 0 else old

        consumed = -modifier
        return InputBank(direction(self.left, horizontal == -1),
                         direction(self.right, horizontal == 1),
                         direction(self.up, vertical == -1),
                         direction(self.down, vertical == 1),
                         consumed if modifier and self.modifier == consumed else modifier)

    def clear_directions(self):
        """ClearControls 4:3e3a keeps the modifier, even when pending."""
        return InputBank(modifier=self.modifier)

    def remap(self, *, facing_right, inverted=False):
        """4:3dfe/3e1c: keyboard bank <-> relative controller bank.

        Apply this involution with the facing captured BEFORE GenCtrl when
        returning to keyboard coordinates, even if GenCtrl turned the actor.
        """
        return InputBank(self.right if facing_right else self.left,
                         self.left if facing_right else self.right,
                         self.down if inverted else self.up,
                         self.up if inverted else self.down, self.modifier)

    def consume(self, *directions, modifier=None, clear=False):
        bank = self.clear_directions() if clear else self
        fields = {name: 1 for name in directions}
        if not set(fields) <= {'left', 'right', 'up', 'down'}:
            raise ValueError('Invalid direction to consume')
        if modifier is not None:
            if modifier not in (1, 2):
                raise ValueError('Invalid consumed modifier')
            fields['modifier'] = modifier
        return replace(bank, **fields)

    def words(self):
        return self.left, self.right, self.up, self.down, self.modifier
