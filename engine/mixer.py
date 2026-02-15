"""Polyphonic mixer with stereo cathedral reverb and warm saturation.

Thread safety: GUI thread sends events via SimpleQueue. Audio callback
drains queue and renders voices. Stereo Schroeder reverb with two
independent reverb units (different delay sets for L/R) creates
immense cathedral width. Sub-bass room resonance adds the feeling
of being inside a massive stone building.
"""

from dataclasses import dataclass
from enum import Enum
from queue import SimpleQueue
from typing import Any

import numpy as np

from engine.organ import OrganVoice
from stops.profiles import STOP_REGISTRY, STOP_DEFS, HarmonicProfile, StopDefinition


class EventType(Enum):
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    DRAWBAR_CHANGE = "drawbar_change"
    STOP_TOGGLE = "stop_toggle"


@dataclass
class AudioEvent:
    type: EventType
    data: Any = None


class CombFilter:
    """Vectorized comb filter with low-pass damping for natural reverb decay."""

    __slots__ = ("_buffer", "_size", "_pos", "_feedback", "_damp", "_last")

    def __init__(self, delay_samples: int, feedback: float = 0.7,
                 damping: float = 0.3) -> None:
        self._buffer = np.zeros(delay_samples, dtype=np.float32)
        self._size = delay_samples
        self._pos = 0
        self._feedback = feedback
        self._damp = damping
        self._last = 0.0  # For one-pole low-pass

    def process(self, input_signal: np.ndarray) -> np.ndarray:
        n = len(input_signal)
        output = np.empty(n, dtype=np.float32)

        remaining = n
        in_pos = 0

        while remaining > 0:
            chunk = min(remaining, self._size - self._pos)

            # Read delayed samples
            delayed = self._buffer[self._pos : self._pos + chunk].copy()
            output[in_pos : in_pos + chunk] = delayed

            # Apply one-pole low-pass filter to feedback (damping)
            # This simulates air absorption — high frequencies decay faster
            filtered = np.empty(chunk, dtype=np.float32)
            last = self._last
            damp = self._damp
            for j in range(chunk):
                last = delayed[j] * (1.0 - damp) + last * damp
                filtered[j] = last
            self._last = last

            # Write new samples with filtered feedback
            self._buffer[self._pos : self._pos + chunk] = (
                input_signal[in_pos : in_pos + chunk]
                + filtered * self._feedback
            )

            self._pos = (self._pos + chunk) % self._size
            in_pos += chunk
            remaining -= chunk

        return output


class AllpassFilter:
    """Vectorized allpass filter for reverb diffusion."""

    __slots__ = ("_buffer", "_size", "_pos", "_gain")

    def __init__(self, delay_samples: int, gain: float = 0.5) -> None:
        self._buffer = np.zeros(delay_samples, dtype=np.float32)
        self._size = delay_samples
        self._pos = 0
        self._gain = gain

    def process(self, input_signal: np.ndarray) -> np.ndarray:
        n = len(input_signal)
        output = np.empty(n, dtype=np.float32)

        remaining = n
        in_pos = 0

        while remaining > 0:
            chunk = min(remaining, self._size - self._pos)

            delayed = self._buffer[self._pos : self._pos + chunk]
            v = input_signal[in_pos : in_pos + chunk] - self._gain * delayed
            output[in_pos : in_pos + chunk] = delayed + self._gain * v
            self._buffer[self._pos : self._pos + chunk] = v

            self._pos = (self._pos + chunk) % self._size
            in_pos += chunk
            remaining -= chunk

        return output


class CathedralReverb:
    """Enhanced Schroeder reverb with extra diffusion for cathedral ambiance.

    6 parallel comb filters (with damping) + 4 series allpass filters.
    Longer delays and more diffusion than a standard room reverb.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        room_size: float = 0.85,
        wet: float = 0.22,
        base_delays: list[int] | None = None,
        feedback: float = 0.82,
        damping: float = 0.35,
        predelay_ms: float = 18.0,
    ) -> None:
        if base_delays is None:
            base_delays = [1687, 1601, 2053, 1867, 1511, 1327]
        scale = room_size

        self._combs = [
            CombFilter(int(d * scale), feedback=feedback, damping=damping)
            for d in base_delays
        ]

        # More allpass stages for better diffusion (less metallic)
        self._allpasses = [
            AllpassFilter(241, gain=0.6),
            AllpassFilter(557, gain=0.55),
            AllpassFilter(373, gain=0.5),
            AllpassFilter(167, gain=0.45),
        ]

        self._wet = wet
        self._dry = 1.0 - wet

        # Pre-delay: simulates distance from sound source to first reflection
        self._predelay_samples = max(1, int(predelay_ms * sample_rate / 1000))
        self._predelay_buf = np.zeros(self._predelay_samples, dtype=np.float32)
        self._predelay_pos = 0

    def _predelay(self, signal: np.ndarray) -> np.ndarray:
        """Simple delay line for reverb pre-delay."""
        n = len(signal)
        output = np.empty(n, dtype=np.float32)
        remaining = n
        in_pos = 0

        while remaining > 0:
            chunk = min(remaining, self._predelay_samples - self._predelay_pos)
            output[in_pos:in_pos + chunk] = self._predelay_buf[
                self._predelay_pos:self._predelay_pos + chunk
            ]
            self._predelay_buf[
                self._predelay_pos:self._predelay_pos + chunk
            ] = signal[in_pos:in_pos + chunk]
            self._predelay_pos = (self._predelay_pos + chunk) % self._predelay_samples
            in_pos += chunk
            remaining -= chunk

        return output

    def process(self, signal: np.ndarray) -> np.ndarray:
        # Pre-delay
        delayed = self._predelay(signal)

        # Sum parallel comb outputs
        reverb = np.zeros_like(signal)
        for comb in self._combs:
            reverb += comb.process(delayed)
        reverb /= len(self._combs)

        # Series allpass for diffusion
        for ap in self._allpasses:
            reverb = ap.process(reverb)

        return signal * self._dry + reverb * self._wet


class StereoReverb:
    """Stereo cathedral reverb — two independent reverb units with different
    delay characteristics for left and right channels. Creates massive
    spatial width like being inside a real cathedral.
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        # Left channel: slightly shorter delays, less pre-delay
        self._left = CathedralReverb(
            sample_rate,
            room_size=0.90,
            wet=0.28,
            base_delays=[1687, 1601, 2053, 1867, 1511, 1327],
            feedback=0.84,
            damping=0.32,
            predelay_ms=16.0,
        )
        # Right channel: slightly longer delays, more pre-delay
        # Different prime-number delays create decorrelated reflections
        self._right = CathedralReverb(
            sample_rate,
            room_size=0.93,
            wet=0.28,
            base_delays=[1747, 1663, 2111, 1931, 1559, 1381],
            feedback=0.84,
            damping=0.33,
            predelay_ms=22.0,
        )

    def process(self, mono_signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Process mono input → stereo output (left, right)."""
        left = self._left.process(mono_signal)
        right = self._right.process(mono_signal)
        return left, right


class RoomResonance:
    """Sub-bass cathedral room resonance — the ambient hum of a massive space.

    Real cathedrals have natural resonant frequencies determined by their
    dimensions. This generates a very subtle, slowly evolving low-frequency
    drone that reacts to the input signal level.
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        self._sample_rate = sample_rate
        self._phase1 = 0.0
        self._phase2 = 0.0
        # Room resonance frequencies (very low — you feel these more than hear)
        self._freq1 = 32.0   # ~C1 — typical large cathedral resonance
        self._freq2 = 48.0   # ~G1 — fifth above
        self._level = 0.0
        self._level_smooth = 0.0

    def process(self, signal: np.ndarray, has_active_voices: bool) -> np.ndarray:
        """Add subtle room resonance proportional to signal energy."""
        n = len(signal)

        # Track signal level with slow follower
        if has_active_voices:
            target = 0.012  # Subtle but present
        else:
            target = 0.0

        # Very slow attack/release for the resonance envelope
        if target > self._level_smooth:
            self._level_smooth += (target - self._level_smooth) * 0.0005
        else:
            self._level_smooth += (target - self._level_smooth) * 0.0001

        if self._level_smooth < 0.0001:
            return signal

        t = np.arange(n, dtype=np.float64)

        # Two low-frequency tones with slow beating
        res1 = np.sin(
            2 * np.pi * self._freq1 * t / self._sample_rate + self._phase1
        ).astype(np.float32)
        res2 = np.sin(
            2 * np.pi * self._freq2 * t / self._sample_rate + self._phase2
        ).astype(np.float32)

        self._phase1 += 2 * np.pi * self._freq1 * n / self._sample_rate
        self._phase2 += 2 * np.pi * self._freq2 * n / self._sample_rate
        self._phase1 %= (2 * np.pi)
        self._phase2 %= (2 * np.pi)

        resonance = (res1 * 0.6 + res2 * 0.4) * self._level_smooth
        return signal + resonance


class Mixer:
    """Polyphonic mixer with stereo cathedral reverb and room resonance."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self.event_queue: SimpleQueue[AudioEvent] = SimpleQueue()

        self._voices: dict[int, OrganVoice] = {}

        # FULL CATHEDRAL REGISTRATION — maximum grandeur
        self._drawbar_values: list[float] = [
            1.0,  # 16' - Sub-octave foundation (FULL for grandeur)
            1.0,  # 8'  - Fundamental
            0.7,  # 5⅓' - Quint warmth and complexity
            0.85, # 4'  - Octave reinforcement
            0.5,  # 2⅔' - Second quint richness
            0.65, # 2'  - Upper octave brilliance
            0.35, # 1⅗' - Tierce color
            0.3,  # 1⅓' - Larigot shimmer
            0.25, # 1'  - Top octave sparkle
        ]

        # Start with Principal + Bourdon for a grand foundation
        self._active_stops: dict[str, HarmonicProfile] = {
            "Principal 8'": STOP_REGISTRY["Principal 8'"],
            "Bourdon 16'": STOP_REGISTRY["Bourdon 16'"],
        }

        # Track full stop definitions for voicing
        self._active_stop_defs: dict[str, StopDefinition] = {
            "Principal 8'": STOP_DEFS["Principal 8'"],
            "Bourdon 16'": STOP_DEFS["Bourdon 16'"],
        }

        self._master_volume = 0.32
        self._stereo_reverb = StereoReverb(sample_rate)
        self._room_resonance = RoomResonance(sample_rate)

        # DC blocking filter state (stereo)
        self._dc_x_prev_l = 0.0
        self._dc_y_prev_l = 0.0
        self._dc_x_prev_r = 0.0
        self._dc_y_prev_r = 0.0

    def _dc_block(self, signal: np.ndarray,
                  x_prev: float, y_prev: float) -> tuple[np.ndarray, float, float]:
        """Remove DC offset with a simple high-pass filter."""
        output = np.empty_like(signal)
        R = 0.995

        for i in range(len(signal)):
            output[i] = signal[i] - x_prev + R * y_prev
            x_prev = signal[i]
            y_prev = output[i]

        return output, x_prev, y_prev

    def _process_events(self) -> None:
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
            except Exception:
                break

            if event.type == EventType.NOTE_ON:
                note = event.data
                if note in self._voices:
                    self._voices[note].note_off()
                # Pass stop definitions for per-pipe voicing
                stop_defs = list(self._active_stop_defs.values())
                self._voices[note] = OrganVoice(
                    note, self.sample_rate, stop_defs=stop_defs
                )

            elif event.type == EventType.NOTE_OFF:
                note = event.data
                if note in self._voices:
                    self._voices[note].note_off()

            elif event.type == EventType.DRAWBAR_CHANGE:
                idx, value = event.data
                if 0 <= idx < 9:
                    self._drawbar_values[idx] = value

            elif event.type == EventType.STOP_TOGGLE:
                stop_name = event.data
                if stop_name in self._active_stops:
                    del self._active_stops[stop_name]
                    del self._active_stop_defs[stop_name]
                elif stop_name in STOP_REGISTRY:
                    self._active_stops[stop_name] = STOP_REGISTRY[stop_name]
                    self._active_stop_defs[stop_name] = STOP_DEFS[stop_name]

    def render(self, num_frames: int) -> np.ndarray:
        """Render stereo audio: returns (num_frames, 2) array."""
        self._process_events()

        mono = np.zeros(num_frames, dtype=np.float32)
        stop_profiles = list(self._active_stops.values())

        has_voices = False
        active_count = 0

        if stop_profiles:
            dead_notes: list[int] = []
            for note, voice in self._voices.items():
                if voice.is_active:
                    mono += voice.render(num_frames, self._drawbar_values, stop_profiles)
                    has_voices = True
                    active_count += 1
                else:
                    dead_notes.append(note)

            for note in dead_notes:
                del self._voices[note]

        # Voice normalization: prevent distortion from stacking voices
        # Scale by 1/sqrt(n) — keeps single notes full, chords balanced
        if active_count > 1:
            mono /= np.sqrt(active_count).astype(np.float32)

        # Add sub-bass room resonance (reacts to playing)
        mono = self._room_resonance.process(mono, has_voices)

        # Stereo cathedral reverb
        left, right = self._stereo_reverb.process(mono)

        # DC blocking (stereo)
        left, self._dc_x_prev_l, self._dc_y_prev_l = self._dc_block(
            left, self._dc_x_prev_l, self._dc_y_prev_l
        )
        right, self._dc_x_prev_r, self._dc_y_prev_r = self._dc_block(
            right, self._dc_x_prev_r, self._dc_y_prev_r
        )

        # Warm saturation (tube-style soft clipping) — stereo
        def _saturate(signal: np.ndarray) -> np.ndarray:
            scaled = signal * self._master_volume
            return np.where(
                np.abs(scaled) < 0.5,
                scaled,
                np.sign(scaled) * (1.0 - np.exp(-2.0 * np.abs(scaled))) * 0.7
            ).astype(np.float32)

        left = _saturate(left)
        right = _saturate(right)

        # Pack into stereo array
        stereo = np.column_stack((left, right))
        return stereo

    # ── Convenience methods for the GUI thread ──────────────────────

    def note_on(self, note: int) -> None:
        self.event_queue.put(AudioEvent(EventType.NOTE_ON, note))

    def note_off(self, note: int) -> None:
        self.event_queue.put(AudioEvent(EventType.NOTE_OFF, note))

    def set_drawbar(self, index: int, value: float) -> None:
        self.event_queue.put(AudioEvent(EventType.DRAWBAR_CHANGE, (index, value)))

    def toggle_stop(self, stop_name: str) -> None:
        self.event_queue.put(AudioEvent(EventType.STOP_TOGGLE, stop_name))

    @property
    def active_stop_names(self) -> set[str]:
        return set(self._active_stops.keys())

    @property
    def drawbar_values(self) -> list[float]:
        return list(self._drawbar_values)
