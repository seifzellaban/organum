"""Organ voice — renders a single note with realistic pipe characteristics.

Each OrganVoice uses stop-specific waveforms, detuning, chiff, tracker
action noise, and per-pipe randomization for a living, breathing sound.
"""

import numpy as np
from engine.oscillator import Oscillator
from engine.envelope import Envelope
from stops.profiles import StopDefinition, DRAWBAR_HARMONICS, STOP_DEFS

# MIDI note number → frequency (A4 = 440 Hz, equal temperament)
def midi_to_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


# Pre-compute a bandpass-filtered noise table for chiff (reusable)
_CHIFF_TABLE_SIZE = 44100  # 1 second at 44.1kHz
_rng = np.random.default_rng(42)
_raw_chiff = _rng.standard_normal(_CHIFF_TABLE_SIZE).astype(np.float32)
# Simple high-pass: subtract smoothed version to keep only sizzle
_smooth = np.convolve(_raw_chiff, np.ones(8) / 8, mode='same')
CHIFF_TABLE = (_raw_chiff - _smooth * 0.7).astype(np.float32)
CHIFF_TABLE /= np.max(np.abs(CHIFF_TABLE))


class OrganVoice:
    """A single sounding note with per-stop voicing characteristics."""

    __slots__ = (
        "note", "_fundamental", "_oscillators_a", "_oscillators_b",
        "_envelope", "_sample_rate", "_chiff_samples_left", "_chiff_pos",
        "_noise_level", "_chiff_amount", "_stop_waveform",
        "_tracker_click_left", "_tracker_click_phase",
        "_wind_flutter_phase", "_wind_flutter_rate",
    )

    # Tracker action click — the mechanical sound of the key valve opening
    TRACKER_CLICK_MS = 2.0
    TRACKER_CLICK_LEVEL = 0.006

    def __init__(
        self,
        note: int,
        sample_rate: int = 44100,
        stop_defs: list[StopDefinition] | None = None,
    ) -> None:
        self.note = note
        self._fundamental = midi_to_freq(note)
        self._sample_rate = sample_rate

        # Blend voicing parameters from active stops
        if stop_defs and len(stop_defs) > 0:
            n = len(stop_defs)
            chorus_detune = sum(s.chorus_detune for s in stop_defs) / n
            vibrato_depth = sum(s.vibrato_depth for s in stop_defs) / n
            vibrato_rate = sum(s.vibrato_rate for s in stop_defs) / n
            self._chiff_amount = sum(s.chiff_amount for s in stop_defs) / n * 0.6
            chiff_ms = sum(s.chiff_ms for s in stop_defs) / n
            self._noise_level = sum(s.wind_noise for s in stop_defs) / n
            attack_ms = sum(s.attack_ms for s in stop_defs) / n
            release_ms = sum(s.release_ms for s in stop_defs) / n
            # Use the first stop's waveform (primary voice)
            waveform = stop_defs[0].waveform
        else:
            chorus_detune = 0.8
            vibrato_depth = 0.6
            vibrato_rate = 5.8
            self._chiff_amount = 0.012
            chiff_ms = 15.0
            self._noise_level = 0.004
            attack_ms = 35.0
            release_ms = 350.0
            waveform = "principal"

        self._stop_waveform = waveform

        # Per-pipe randomization: real organs have slight variations
        pipe_rand = np.random.default_rng(note * 31 + 7)
        detune_variation = 1.0 + pipe_rand.uniform(-0.15, 0.15)
        vibrato_variation = 1.0 + pipe_rand.uniform(-0.1, 0.1)
        attack_variation = 1.0 + pipe_rand.uniform(-0.2, 0.2)

        actual_detune = chorus_detune * detune_variation
        actual_vibrato_depth = vibrato_depth * vibrato_variation
        actual_attack = max(3.0, attack_ms * attack_variation)

        self._envelope = Envelope(
            sample_rate=sample_rate,
            attack_ms=actual_attack,
            decay_ms=60.0,
            sustain=0.88,
            release_ms=release_ms,
            attack_curve=1.6,
        )

        nyquist = sample_rate / 2.0

        # Two sets of oscillators for chorus — using the stop's waveform
        self._oscillators_a: list[Oscillator | None] = []
        self._oscillators_b: list[Oscillator | None] = []

        for h in DRAWBAR_HARMONICS:
            freq = self._fundamental * h
            if freq < nyquist:
                self._oscillators_a.append(
                    Oscillator(freq, sample_rate,
                              vibrato_depth=actual_vibrato_depth,
                              vibrato_rate=vibrato_rate,
                              waveform=waveform)
                )
                # Chorus partner — slightly different waveform and detuning
                self._oscillators_b.append(
                    Oscillator(freq + actual_detune, sample_rate,
                              vibrato_depth=actual_vibrato_depth * 0.7,
                              vibrato_rate=vibrato_rate * 1.07,
                              waveform=waveform)
                )
            else:
                self._oscillators_a.append(None)
                self._oscillators_b.append(None)

        # Chiff: high-frequency pipe speech transient
        self._chiff_samples_left = int(chiff_ms * sample_rate / 1000)
        self._chiff_pos = pipe_rand.integers(0, _CHIFF_TABLE_SIZE - 4096)

        # Tracker click: brief mechanical impulse
        self._tracker_click_left = int(self.TRACKER_CLICK_MS * sample_rate / 1000)
        self._tracker_click_phase = 0.0

        # Wind flutter: slow random modulation of amplitude
        self._wind_flutter_phase = pipe_rand.uniform(0, 2 * np.pi)
        self._wind_flutter_rate = pipe_rand.uniform(0.3, 0.8)  # Very slow

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
        stop_profiles: list[dict[int, float]],
    ) -> np.ndarray:
        """Render audio with chorus, chiff, tracker action, and wind noise."""
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

        # Tracker click: very brief mechanical impulse at note start
        if self._tracker_click_left > 0:
            n = min(num_frames, self._tracker_click_left)
            t = np.arange(n, dtype=np.float32) + self._tracker_click_phase
            # Mix of high-frequency components for mechanical click
            click = (
                np.sin(2 * np.pi * 3200 * t / self._sample_rate) * 0.6 +
                np.sin(2 * np.pi * 5800 * t / self._sample_rate) * 0.3 +
                np.sin(2 * np.pi * 8400 * t / self._sample_rate) * 0.1
            ).astype(np.float32)
            click_env = np.exp(-8.0 * np.arange(n, dtype=np.float32) / n)
            output[:n] += click * click_env * self.TRACKER_CLICK_LEVEL
            self._tracker_click_phase += n
            self._tracker_click_left -= n

        # Chiff: shaped high-frequency noise burst during pipe speech
        if self._chiff_samples_left > 0:
            n = min(num_frames, self._chiff_samples_left)
            # Read from pre-computed chiff table
            end_pos = min(self._chiff_pos + n, _CHIFF_TABLE_SIZE)
            actual_n = end_pos - self._chiff_pos
            if actual_n > 0:
                chiff_noise = CHIFF_TABLE[self._chiff_pos:end_pos].copy()
                # Shape the chiff: fast rise, exponential decay
                chiff_t = np.arange(actual_n, dtype=np.float32) / actual_n
                chiff_env = np.exp(-4.0 * chiff_t) * (1.0 - np.exp(-20.0 * chiff_t))
                output[:actual_n] += chiff_noise * chiff_env * self._chiff_amount
                self._chiff_pos += actual_n
            self._chiff_samples_left -= n

        # Wind flutter: slow amplitude modulation for "breathing" quality
        t_frames = np.arange(num_frames, dtype=np.float32)
        flutter = 1.0 + 0.004 * np.sin(
            2 * np.pi * self._wind_flutter_rate * t_frames / self._sample_rate
            + self._wind_flutter_phase
        )
        self._wind_flutter_phase += (
            2 * np.pi * self._wind_flutter_rate * num_frames / self._sample_rate
        )
        output *= flutter

        # Subtle wind noise (continuous, very low amplitude with variation)
        if self._noise_level > 0:
            noise = np.random.randn(num_frames).astype(np.float32)
            # Shape noise to be slightly frequency-dependent (higher notes = brighter noise)
            if self._fundamental > 800:
                output += noise * self._noise_level * 1.3
            else:
                # Low-pass the noise for lower notes
                noise = np.convolve(noise, np.ones(3) / 3, mode='same').astype(np.float32)
                output += noise * self._noise_level

        # Apply envelope
        env = self._envelope.render(num_frames)
        output *= env

        return output
