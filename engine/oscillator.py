"""Wavetable oscillator with optional chorus detuning and vibrato.

Pre-computes a single period of sine, uses a phase accumulator for
glitch-free playback, and supports subtle detuning for chorus richness.
"""

import numpy as np

# Wavetable size — power of 2 for fast modulo via bitwise AND
TABLE_SIZE = 4096
TABLE_MASK = TABLE_SIZE - 1

# Pre-compute one period of sine
_SINE_TABLE = np.sin(2.0 * np.pi * np.arange(TABLE_SIZE) / TABLE_SIZE).astype(np.float32)


class Oscillator:
    """Phase-accumulator oscillator with optional chorus and vibrato."""

    __slots__ = (
        "_phase", "_phase_inc", "_sample_rate", "_frequency",
        "_vibrato_depth", "_vibrato_rate", "_vibrato_phase",
    )

    def __init__(
        self,
        frequency: float,
        sample_rate: int = 44100,
        vibrato_depth: float = 0.0,
        vibrato_rate: float = 5.5,
    ) -> None:
        self._sample_rate = sample_rate
        self._frequency = frequency
        self._phase = np.random.uniform(0, TABLE_SIZE)  # Random start for chorus
        self._phase_inc = frequency * TABLE_SIZE / sample_rate
        self._vibrato_depth = vibrato_depth  # In Hz
        self._vibrato_rate = vibrato_rate     # LFO rate in Hz
        self._vibrato_phase = np.random.uniform(0, 2 * np.pi)

    def set_frequency(self, frequency: float) -> None:
        self._frequency = frequency
        self._phase_inc = frequency * TABLE_SIZE / self._sample_rate

    def render(self, num_frames: int) -> np.ndarray:
        """Generate num_frames samples with optional vibrato."""
        t = np.arange(num_frames, dtype=np.float64)

        if self._vibrato_depth > 0:
            # LFO modulates frequency
            lfo = np.sin(
                2 * np.pi * self._vibrato_rate * t / self._sample_rate + self._vibrato_phase
            )
            freq_mod = self._frequency + self._vibrato_depth * lfo
            phase_incs = freq_mod * TABLE_SIZE / self._sample_rate
            phases = self._phase + np.cumsum(phase_incs)
            self._vibrato_phase += 2 * np.pi * self._vibrato_rate * num_frames / self._sample_rate
        else:
            phases = self._phase + self._phase_inc * t

        # Wrap phase
        phases = phases % TABLE_SIZE

        # Linear interpolation
        idx = phases.astype(np.int32)
        frac = (phases - idx).astype(np.float32)
        idx_next = (idx + 1) & TABLE_MASK

        samples = _SINE_TABLE[idx] * (1.0 - frac) + _SINE_TABLE[idx_next] * frac

        # Advance phase state
        self._phase = phases[-1] + (self._phase_inc if self._vibrato_depth == 0
                                     else phase_incs[-1])
        self._phase = self._phase % TABLE_SIZE

        return samples
