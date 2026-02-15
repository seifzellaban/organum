"""ADSR envelope generator — fully vectorized for performance.

No per-sample Python loops. Each stage is computed as a numpy array
slice in one shot.
"""

import numpy as np
from enum import IntEnum


class Stage(IntEnum):
    IDLE = 0
    ATTACK = 1
    DECAY = 2
    SUSTAIN = 3
    RELEASE = 4


class Envelope:
    """Per-voice ADSR envelope with organ-appropriate defaults."""

    __slots__ = (
        "_stage",
        "_level",
        "_attack_rate",
        "_decay_rate",
        "_sustain_level",
        "_release_rate",
        "_sample_rate",
    )

    def __init__(
        self,
        sample_rate: int = 44100,
        attack_ms: float = 8.0,
        decay_ms: float = 30.0,
        sustain: float = 0.85,
        release_ms: float = 120.0,
    ) -> None:
        self._sample_rate = sample_rate
        self._stage = Stage.IDLE
        self._level = 0.0

        # Rates = level change per sample
        self._attack_rate = 1.0 / max(1, int(attack_ms * sample_rate / 1000))
        self._decay_rate = (1.0 - sustain) / max(1, int(decay_ms * sample_rate / 1000))
        self._sustain_level = sustain
        self._release_rate = sustain / max(1, int(release_ms * sample_rate / 1000))

    def note_on(self) -> None:
        self._stage = Stage.ATTACK

    def note_off(self) -> None:
        if self._stage != Stage.IDLE:
            self._stage = Stage.RELEASE

    @property
    def is_active(self) -> bool:
        return self._stage != Stage.IDLE

    def render(self, num_frames: int) -> np.ndarray:
        """Vectorized envelope rendering — no per-sample loop."""
        out = np.empty(num_frames, dtype=np.float32)
        pos = 0

        while pos < num_frames:
            remaining = num_frames - pos

            if self._stage == Stage.ATTACK:
                # How many samples to reach 1.0?
                samples_to_peak = int((1.0 - self._level) / self._attack_rate) + 1
                n = min(remaining, samples_to_peak)
                end_level = min(1.0, self._level + self._attack_rate * n)
                out[pos:pos + n] = np.linspace(self._level, end_level, n, dtype=np.float32)
                self._level = end_level
                pos += n
                if self._level >= 1.0:
                    self._level = 1.0
                    self._stage = Stage.DECAY

            elif self._stage == Stage.DECAY:
                samples_to_sustain = int((self._level - self._sustain_level) / self._decay_rate) + 1
                n = min(remaining, samples_to_sustain)
                end_level = max(self._sustain_level, self._level - self._decay_rate * n)
                out[pos:pos + n] = np.linspace(self._level, end_level, n, dtype=np.float32)
                self._level = end_level
                pos += n
                if self._level <= self._sustain_level:
                    self._level = self._sustain_level
                    self._stage = Stage.SUSTAIN

            elif self._stage == Stage.SUSTAIN:
                out[pos:pos + remaining] = self._sustain_level
                pos += remaining

            elif self._stage == Stage.RELEASE:
                samples_to_zero = int(self._level / self._release_rate) + 1
                n = min(remaining, samples_to_zero)
                end_level = max(0.0, self._level - self._release_rate * n)
                out[pos:pos + n] = np.linspace(self._level, end_level, n, dtype=np.float32)
                self._level = end_level
                pos += n
                if self._level <= 0.0:
                    self._level = 0.0
                    self._stage = Stage.IDLE

            elif self._stage == Stage.IDLE:
                out[pos:pos + remaining] = 0.0
                pos += remaining

        return out
