"""Polyphonic mixer with cathedral reverb and warm saturation.

Thread safety: GUI thread sends events via SimpleQueue. Audio callback
drains queue and renders voices. Enhanced Schroeder reverb with more
diffusion stages for cathedral ambiance. Warm tube-style saturation
instead of hard clipping.
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
        self, sample_rate: int = 44100, room_size: float = 0.85, wet: float = 0.22
    ) -> None:
        # Use more comb filters with prime-number delays for dense reverb
        # These delays are tuned for a large cathedral space
        base_delays = [1687, 1601, 2053, 1867, 1511, 1327]
        scale = room_size

        # Higher feedback + damping = longer, warmer reverb tail
        self._combs = [
            CombFilter(int(d * scale), feedback=0.82, damping=0.35)
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
        self._predelay_samples = int(0.018 * sample_rate)  # 18ms
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


class Mixer:
    """Polyphonic mixer owning all active voices and current organ state."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self.event_queue: SimpleQueue[AudioEvent] = SimpleQueue()

        self._voices: dict[int, OrganVoice] = {}

        # GRAND CATHEDRAL REGISTRATION - Full, rich, majestic
        self._drawbar_values: list[float] = [
            0.8,  # 16' - Sub-octave foundation
            1.0,  # 8'  - Fundamental
            0.6,  # 5⅓' - Quint adds warmth
            0.8,  # 4'  - Octave reinforcement
            0.4,  # 2⅔' - Second quint
            0.6,  # 2'  - Upper octave brilliance
            0.3,  # 1⅗' - Tierce for color
            0.25, # 1⅓' - Larigot shimmer
            0.2,  # 1'  - Top octave sparkle
        ]

        self._active_stops: dict[str, HarmonicProfile] = {
            "Principal 8'": STOP_REGISTRY["Principal 8'"],
        }

        # Track full stop definitions for voicing
        self._active_stop_defs: dict[str, StopDefinition] = {
            "Principal 8'": STOP_DEFS["Principal 8'"],
        }

        self._master_volume = 0.35
        self._reverb = CathedralReverb(sample_rate, room_size=0.85, wet=0.22)

        # DC blocking filter state
        self._dc_x_prev = 0.0
        self._dc_y_prev = 0.0

    def _dc_block(self, signal: np.ndarray) -> np.ndarray:
        """Remove DC offset with a simple high-pass filter."""
        output = np.empty_like(signal)
        x_prev = self._dc_x_prev
        y_prev = self._dc_y_prev
        R = 0.995  # Very close to 1 for minimal effect on audio

        for i in range(len(signal)):
            output[i] = signal[i] - x_prev + R * y_prev
            x_prev = signal[i]
            y_prev = output[i]

        self._dc_x_prev = x_prev
        self._dc_y_prev = y_prev
        return output

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
        self._process_events()

        output = np.zeros(num_frames, dtype=np.float32)
        stop_profiles = list(self._active_stops.values())

        if not stop_profiles:
            return output

        dead_notes: list[int] = []
        for note, voice in self._voices.items():
            if voice.is_active:
                output += voice.render(num_frames, self._drawbar_values, stop_profiles)
            else:
                dead_notes.append(note)

        for note in dead_notes:
            del self._voices[note]

        # DC blocking (removes any accumulated DC offset)
        output = self._dc_block(output)

        # Apply cathedral reverb
        output = self._reverb.process(output)

        # Warm saturation (tube-style soft clipping)
        # More musical than hard tanh — preserves dynamics better
        scaled = output * self._master_volume
        output = np.where(
            np.abs(scaled) < 0.5,
            scaled,  # Linear region for quiet signals
            np.sign(scaled) * (1.0 - np.exp(-2.0 * np.abs(scaled))) * 0.7
        )

        return output.astype(np.float32)

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
