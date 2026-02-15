"""Organ voice — renders a single note with harmonics, chorus, chiff, and wind noise.

Each OrganVoice owns oscillator pairs (slightly detuned for chorus),
an ADSR envelope, and generates a subtle attack chiff and wind noise.
"""

import numpy as np
from engine.oscillator import Oscillator
from engine.envelope import Envelope
from stops.profiles import HarmonicProfile, DRAWBAR_HARMONICS

# MIDI note number → frequency (A4 = 440 Hz, equal temperament)
def midi_to_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


class OrganVoice:
    """A single sounding note with chorus detuning, chiff, and wind noise."""

    __slots__ = (
        "note", "_fundamental", "_oscillators_a", "_oscillators_b",
        "_envelope", "_sample_rate", "_chiff_envelope", "_chiff_samples_left",
        "_noise_level",
    )

    # Chorus detune amount in Hz (slight beating)
    CHORUS_DETUNE = 0.8
    # Vibrato depth and rate (subtle tremulant)
    VIBRATO_DEPTH = 0.6
    VIBRATO_RATE = 5.8
    # Chiff duration in samples (very brief)
    CHIFF_DURATION_MS = 10.0
    # Wind noise level
    WIND_NOISE = 0.008

    def __init__(self, note: int, sample_rate: int = 44100) -> None:
        self.note = note
        self._fundamental = midi_to_freq(note)
        self._sample_rate = sample_rate
        self._envelope = Envelope(sample_rate=sample_rate)
        self._noise_level = self.WIND_NOISE

        nyquist = sample_rate / 2.0

        # Create two sets of oscillators for chorus (slightly detuned)
        self._oscillators_a: list[Oscillator | None] = []
        self._oscillators_b: list[Oscillator | None] = []

        for h in DRAWBAR_HARMONICS:
            freq = self._fundamental * h
            if freq < nyquist:
                self._oscillators_a.append(
                    Oscillator(freq, sample_rate,
                              vibrato_depth=self.VIBRATO_DEPTH,
                              vibrato_rate=self.VIBRATO_RATE)
                )
                self._oscillators_b.append(
                    Oscillator(freq + self.CHORUS_DETUNE, sample_rate,
                              vibrato_depth=self.VIBRATO_DEPTH * 0.7,
                              vibrato_rate=self.VIBRATO_RATE * 1.1)
                )
            else:
                self._oscillators_a.append(None)
                self._oscillators_b.append(None)

        # Chiff: brief noise burst on attack
        self._chiff_samples_left = int(self.CHIFF_DURATION_MS * sample_rate / 1000)

        self._envelope.note_on()

    def note_off(self) -> None:
        self._envelope.note_off()

    @property
    def is_active(self) -> bool:
        return self._envelope.is_active

    def render(
        self,
        num_frames: int,
        drawbar_values: list[float],
        stop_profiles: list[HarmonicProfile],
    ) -> np.ndarray:
        """Render audio with chorus, chiff, and wind noise."""
        # Pre-compute effective amplitude per drawbar harmonic
        harmonic_amps = np.zeros(len(DRAWBAR_HARMONICS), dtype=np.float32)

        for profile in stop_profiles:
            for i, h in enumerate(DRAWBAR_HARMONICS):
                h_int = int(round(h)) if h >= 1 else 1
                if h_int in profile:
                    harmonic_amps[i] += profile[h_int] * drawbar_values[i]

        # Normalize if multiple stops
        if len(stop_profiles) > 1:
            max_amp = harmonic_amps.max()
            if max_amp > 1.0:
                harmonic_amps /= max_amp

        # Sum oscillator pairs (chorus)
        output = np.zeros(num_frames, dtype=np.float32)
        for i in range(len(DRAWBAR_HARMONICS)):
            if harmonic_amps[i] < 0.001:
                continue
            amp = harmonic_amps[i]
            osc_a = self._oscillators_a[i]
            osc_b = self._oscillators_b[i]
            if osc_a is not None:
                output += osc_a.render(num_frames) * (amp * 0.55)
            if osc_b is not None:
                output += osc_b.render(num_frames) * (amp * 0.45)

        # Add chiff (attack transient — very subtle noise burst)
        if self._chiff_samples_left > 0:
            n = min(num_frames, self._chiff_samples_left)
            chiff_noise = np.random.randn(n).astype(np.float32) * 0.03  # Much quieter
            # Smooth fade out
            chiff_env = np.linspace(1.0, 0.0, n, dtype=np.float32) ** 3  # Steeper curve
            output[:n] += chiff_noise * chiff_env
            self._chiff_samples_left -= n

        # Add subtle wind noise (continuous, very low amplitude)
        if self._noise_level > 0:
            output += np.random.randn(num_frames).astype(np.float32) * self._noise_level

        # Apply envelope
        env = self._envelope.render(num_frames)
        output *= env

        return output
