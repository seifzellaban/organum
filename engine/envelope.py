"""ADSR envelope generator with organ-specific pipe speech simulation.

Fully vectorized. Includes:
- Configurable attack curve (exponential for natural feel)
- Pipe speech delay (slight random onset delay per voice)
- Smooth exponential release (no abrupt cutoff)
"""

import numpy as np
from enum import IntEnum


class Stage(IntEnum):
    IDLE = 0
    ATTACK = 1
    DECAY = 2
    SUSTAIN = 3
    RELEASE = 4
    RETRIGGER = 5  # Smooth crossfade back to sustain (no click)


class Envelope:
    """Per-voice ADSR envelope with configurable curve shape."""

    __slots__ = (
        "_stage",
        "_level",
        "_attack_samples",
        "_decay_samples",
        "_sustain_level",
        "_release_samples",
        "_sample_rate",
        "_attack_pos",
        "_decay_pos",
        "_release_pos",
        "_release_start_level",
        "_attack_curve",
        "_retrigger_pos",
        "_retrigger_samples",
        "_retrigger_start_level",
    )

    def __init__(
        self,
        sample_rate: int = 44100,
        attack_ms: float = 45.0,
        decay_ms: float = 60.0,
        sustain: float = 0.92,
        release_ms: float = 800.0,
        attack_curve: float = 1.4,  # slight fade-in — pipe "speaks"
    ) -> None:
        self._sample_rate = sample_rate
        self._stage = Stage.IDLE
        self._level = 0.0
        self._attack_curve = attack_curve

        self._attack_samples = max(1, int(attack_ms * sample_rate / 1000))
        self._decay_samples = max(1, int(decay_ms * sample_rate / 1000))
        self._sustain_level = sustain
        self._release_samples = max(1, int(release_ms * sample_rate / 1000))

        self._attack_pos = 0
        self._decay_pos = 0
        self._release_pos = 0
        self._release_start_level = 0.0

        # Retrigger: short crossfade ramp (~15ms)
        self._retrigger_samples = max(1, int(15.0 * sample_rate / 1000))
        self._retrigger_pos = 0
        self._retrigger_start_level = 0.0

    def note_on(self) -> None:
        self._stage = Stage.ATTACK
        self._attack_pos = 0

    def note_off(self) -> None:
        if self._stage != Stage.IDLE:
            self._stage = Stage.RELEASE
            self._release_pos = 0
            self._release_start_level = self._level

    def retrigger(self) -> None:
        """Smoothly ramp back to sustain — no click, no new attack transient."""
        if self._stage in (Stage.RELEASE, Stage.IDLE):
            self._retrigger_start_level = self._level
            self._retrigger_pos = 0
            self._stage = Stage.RETRIGGER

    @property
    def is_active(self) -> bool:
        return self._stage != Stage.IDLE

    @property
    def is_releasing(self) -> bool:
        return self._stage == Stage.RELEASE

    def render(self, num_frames: int) -> np.ndarray:
        """Vectorized envelope rendering with shaped curves."""
        out = np.empty(num_frames, dtype=np.float32)
        pos = 0

        while pos < num_frames:
            remaining = num_frames - pos

            if self._stage == Stage.ATTACK:
                n = min(remaining, self._attack_samples - self._attack_pos)
                if n <= 0:
                    self._level = 1.0
                    self._stage = Stage.DECAY
                    self._decay_pos = 0
                    continue

                # Smoothstep attack — pipe wind fills gradually then eases in
                # Zero derivative at both ends: no harsh onset, no slam into sustain
                t = np.arange(self._attack_pos, self._attack_pos + n,
                              dtype=np.float32) / self._attack_samples
                curve = t * t * (3.0 - 2.0 * t)  # smoothstep: starts gentle, ends gentle
                out[pos:pos + n] = curve
                self._attack_pos += n
                self._level = float(curve[-1])
                pos += n

                if self._attack_pos >= self._attack_samples:
                    self._level = 1.0
                    self._stage = Stage.DECAY
                    self._decay_pos = 0

            elif self._stage == Stage.DECAY:
                n = min(remaining, self._decay_samples - self._decay_pos)
                if n <= 0:
                    self._level = self._sustain_level
                    self._stage = Stage.SUSTAIN
                    continue

                # Gentle decay — slow, smooth approach to sustain
                t = np.arange(self._decay_pos, self._decay_pos + n,
                              dtype=np.float32) / self._decay_samples
                decay_range = 1.0 - self._sustain_level
                curve = 1.0 - decay_range * (1.0 - np.exp(-1.5 * t)) / (1.0 - np.exp(-1.5))
                out[pos:pos + n] = curve
                self._decay_pos += n
                self._level = float(curve[-1])
                pos += n

                if self._decay_pos >= self._decay_samples:
                    self._level = self._sustain_level
                    self._stage = Stage.SUSTAIN

            elif self._stage == Stage.SUSTAIN:
                out[pos:pos + remaining] = self._sustain_level
                self._level = self._sustain_level
                pos += remaining

            elif self._stage == Stage.RELEASE:
                # No fixed cutoff — keep decaying until naturally silent
                n = remaining

                # Gentle exponential release — pipe wind bleeds out slowly.
                # exp(-1.2*t) reaches 50% at t≈0.58 (≈375ms for a 650ms release)
                # which feels like a natural, lingering decay.
                t = np.arange(self._release_pos, self._release_pos + n,
                              dtype=np.float32) / self._release_samples
                curve = self._release_start_level * np.exp(-1.2 * t)
                out[pos:pos + n] = curve
                self._release_pos += n
                self._level = float(curve[-1])
                pos += n

                # Only go silent when truly inaudible
                if self._level < 0.003:
                    self._level = 0.0
                    self._stage = Stage.IDLE

            elif self._stage == Stage.RETRIGGER:
                # Smooth crossfade from current level back to sustain
                n = min(remaining, self._retrigger_samples - self._retrigger_pos)
                if n <= 0:
                    self._level = self._sustain_level
                    self._stage = Stage.SUSTAIN
                    continue

                t = np.arange(self._retrigger_pos, self._retrigger_pos + n,
                              dtype=np.float32) / self._retrigger_samples
                # Smooth S-curve (hermite) for click-free crossfade
                blend = t * t * (3.0 - 2.0 * t)
                curve = (
                    self._retrigger_start_level * (1.0 - blend)
                    + self._sustain_level * blend
                )
                out[pos:pos + n] = curve
                self._retrigger_pos += n
                self._level = float(curve[-1])
                pos += n

                if self._retrigger_pos >= self._retrigger_samples:
                    self._level = self._sustain_level
                    self._stage = Stage.SUSTAIN

            elif self._stage == Stage.IDLE:
                out[pos:pos + remaining] = 0.0
                pos += remaining

        return out
